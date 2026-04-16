import os
import uuid
import cv2
import time
import csv
import numpy as np
import matplotlib
import math
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, send_file

app = Flask(__name__)

UPLOAD_FOLDER = "static/uploads"
RESULT_FOLDER = "static/results"
DATASET_FOLDER = "static/dataset"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)
os.makedirs(DATASET_FOLDER, exist_ok=True)

from ultralytics import YOLO
model = YOLO("model/last.pt")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tif', 'tiff', 'webp', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_iou(box1, box2):
    x_left = max(box1[0], box2[0])
    y_top = max(box1[1], box2[1])
    x_right = min(box1[2], box2[2])
    y_bottom = min(box1[3], box2[3])

    if x_right < x_left or y_bottom < y_top:
        return 0.0

    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    iou = intersection_area / float(box1_area + box2_area - intersection_area)
    return iou

def generate_advanced_safety_map(image_bgr, craters, tile_size=128):
    h, w = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    tiles_y = h // tile_size
    tiles_x = w // tile_size
    
    if tiles_y == 0 or tiles_x == 0:
        return image_bgr

    metrics = []
    
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            x1 = tx * tile_size
            y1 = ty * tile_size
            x2 = x1 + tile_size
            y2 = y1 + tile_size
            
            tile_area = tile_size * tile_size
            tile_gray = gray[y1:y2, x1:x2]
            
            tile_craters = []
            for c in craters:
                cx, cy = c.get('gx', c.get('x')), c.get('gy', c.get('y'))
                if x1 <= cx < x2 and y1 <= cy < y2:
                    tile_craters.append(c)
                    
            crater_density = len(tile_craters) / tile_area
            diams = [c.get('diameter', 0) for c in tile_craters]
            avg_diameter = float(np.mean(diams)) if len(diams) > 0 else 0.0
            
            roughness = float(np.std(tile_gray))
            mean_intensity = float(np.mean(tile_gray))
            
            metrics.append({
                'tx': tx, 'ty': ty, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                'crater_density': crater_density, 'avg_diameter': avg_diameter,
                'roughness': roughness, 'intensity': mean_intensity
            })
            
    if not metrics:
        return image_bgr

    max_dens = max(m['crater_density'] for m in metrics) or 1.0
    max_diam = max(m['avg_diameter'] for m in metrics) or 1.0
    max_rough = max(m['roughness'] for m in metrics) or 1.0
    
    for m in metrics:
        norm_density = m['crater_density'] / max_dens
        norm_diameter = m['avg_diameter'] / max_diam
        norm_roughness = m['roughness'] / max_rough
        
        score = 0.5 * norm_density + 0.3 * norm_diameter + 0.2 * norm_roughness
        
        maria_threshold = 80
        if m['intensity'] < maria_threshold:
            score *= 0.7 
            
        m['safety_score'] = score
        
    scores = [m['safety_score'] for m in metrics]
    p5 = np.percentile(scores, 5)
    p20 = np.percentile(scores, 20)
    
    grid = np.zeros((tiles_y, tiles_x), dtype=int)
    overlay = np.zeros_like(image_bgr)
    
    for m in metrics:
        s = m['safety_score']
        if s <= p5:
            m['color'] = (0, 255, 0) # GREEN
            grid[m['ty'], m['tx']] = 2
        elif s <= p20:
            m['color'] = (0, 255, 255) # YELLOW
            grid[m['ty'], m['tx']] = 1
        else:
            m['color'] = (0, 0, 255) # RED
            grid[m['ty'], m['tx']] = 0
            
        cv2.rectangle(overlay, (m['x1'], m['y1']), (m['x2'], m['y2']), m['color'], -1)
        
    binary_green = np.uint8(grid == 2)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_green, connectivity=4)
    
    candidates = []
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] >= 4:
            bx = stats[i, cv2.CC_STAT_LEFT]
            by = stats[i, cv2.CC_STAT_TOP]
            bw = stats[i, cv2.CC_STAT_WIDTH]
            bh = stats[i, cv2.CC_STAT_HEIGHT]
            candidates.append((bx*tile_size, by*tile_size, bw*tile_size, bh*tile_size))
            
    blended = cv2.addWeighted(overlay, 0.4, image_bgr, 0.6, 0)
    
    for i, (x, y, w, h) in enumerate(candidates):
        cv2.rectangle(blended, (x, y), (x+w, y+h), (255, 255, 255), 3)
        cv2.putText(blended, f"LZ-{i+1}", (x+5, y+25), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        
    return blended
def process_image(upload_path, filename):
    start_time = time.time()
    results = model(upload_path)
    processing_time = round(time.time() - start_time, 2)
    
    img = cv2.imread(upload_path)
    height, width, _ = img.shape
    image_area = height * width
    
    img_plot = img.copy()
    
    boxes = results[0].boxes
    crater_data = []

    # Terrain Classification (Highlands vs Maria)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean_brightness = np.mean(gray)
    terrain_type = "Highlands (Bright/Rugged)" if mean_brightness > 100 else "Maria (Dark/Smooth)"

    stats = {
        "total": len(boxes),
        "avg_diameter": 0, "largest": 0, "smallest": float('inf'),
        "avg_conf": 0, "density": 0, "time": processing_time,
        "small": 0, "medium": 0, "large": 0,
        "terrain": terrain_type,
        "nw": 0, "ne": 0, "sw": 0, "se": 0
    }

    # Extract all xyxy for IoU
    coords = []
    if len(boxes) > 0:
        coords = boxes.xyxy.tolist()

    overlapping_set = set()
    for i, box1 in enumerate(coords):
        for j, box2 in enumerate(coords):
            if i != j and calculate_iou(box1, box2) > 0.1: # 0.1 IoU threshold for overlap
                overlapping_set.add(i)
                overlapping_set.add(j)

    total_diameter = 0
    total_conf = 0

    csv_data = [["ID", "X_Center", "Y_Center", "Diameter", "Depth_Est", "Morphology", "Confidence", "Quadrant"]]

    for i, box in enumerate(boxes):
        x_c, y_c, w, h = box.xywh[0].tolist()
        conf = float(box.conf[0])
        diameter_px = round(max(w, h), 2)
        depth_px = round(diameter_px * 0.2, 2) # Estimate depth
        
        # Quadrant
        quadrant = "NW" if x_c < width/2 and y_c < height/2 else \
                   "NE" if x_c >= width/2 and y_c < height/2 else \
                   "SW" if x_c < width/2 and y_c >= height/2 else "SE"
        stats[quadrant.lower()] += 1
        
        # Size class
        if diameter_px < 20:
            size_class = "Small"
            stats["small"] += 1
        elif diameter_px < 50:
            size_class = "Medium"
            stats["medium"] += 1
        else:
            size_class = "Large"
            stats["large"] += 1
            
        # Morphology
        morphology = "Simple"
        if diameter_px >= 20: morphology = "Complex"
        aspect_ratio = w / float(h)
        if aspect_ratio > 1.3 or aspect_ratio < 0.7: morphology = "Degraded"
        if i in overlapping_set: morphology += "/Overlapping"
            
        total_diameter += diameter_px
        total_conf += conf
        if diameter_px > stats["largest"]: stats["largest"] = diameter_px
        if diameter_px < stats["smallest"]: stats["smallest"] = diameter_px
        
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        
        crater_data.append({
            "id": i + 1, "diameter": diameter_px, "depth": depth_px,
            "confidence": round(conf, 2), "size": size_class, "morphology": morphology,
            "quadrant": quadrant,
            "x": x_c, "y": y_c, "w": w, "h": h, "x1": x1, "y1": y1, "x2": x2, "y2": y2
        })
        
        csv_data.append([i+1, round(x_c, 2), round(y_c, 2), diameter_px, depth_px, morphology, round(conf, 2), quadrant])
        
        cv2.rectangle(img_plot, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        cv2.circle(img_plot, (int(x_c), int(y_c)), 2, (0, 0, 255), -1)
        cv2.putText(img_plot, f"#{i+1}", (int(x1), int(y1)-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    if stats["total"] > 0:
        stats["avg_diameter"] = round(total_diameter / stats["total"], 2)
        stats["avg_conf"] = round(total_conf / stats["total"], 2)
        stats["density"] = round((stats["total"] / image_area) * 1000000, 2)
    else:
        stats["smallest"] = 0

    # Age Estimation (toy logic based on density)
    if stats["density"] > 500: age = "Imbrian (~3.8 Billion Yrs)"
    elif stats["density"] > 100: age = "Eratosthenian (~3.2 Billion Yrs)"
    else: age = "Copernican (< 1 Billion Yrs)"
    stats["age"] = age

    # Export CSV
    csv_path = os.path.join(DATASET_FOLDER, f"{filename.split('.')[0]}.csv")
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(csv_data)

    result_path = os.path.join(RESULT_FOLDER, filename)
    cv2.imwrite(result_path, img_plot)

    # Visualization & Scientific Mapping
    heatmap_path = os.path.join(RESULT_FOLDER, f"heatmap_{filename}")
    riskmap_path = os.path.join(RESULT_FOLDER, f"riskmap_{filename}")
    chart_path = os.path.join(RESULT_FOLDER, f"chart_{filename}")
    
    # Heatmap
    heatmap = np.zeros((height, width), dtype=np.float32)
    for c in crater_data:
        cv2.circle(heatmap, (int(c["x"]), int(c["y"])), int(c["diameter"]), 1, -1)
    heatmap = cv2.GaussianBlur(heatmap, (51, 51), 0)
    heatmap_norm = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    heatmap_color = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_JET)
    cv2.imwrite(heatmap_path, cv2.addWeighted(img, 0.5, heatmap_color, 0.5, 0))
    # Advanced Landing Safety Map
    advanced_riskmap = generate_advanced_safety_map(img, crater_data, tile_size=64)
    if advanced_riskmap is not None:
        cv2.imwrite(riskmap_path, advanced_riskmap)
    else:
        # Fallback if generation failed
        risk_color = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_AUTUMN)
        cv2.imwrite(riskmap_path, cv2.addWeighted(img, 0.4, risk_color, 0.6, 0))
    
    # Chart
    plt.figure(figsize=(6, 4))
    sizes = [stats["small"], stats["medium"], stats["large"]]
    labels = ["Small", "Medium", "Large"]
    plt.bar(labels, sizes, color=['#4e6ef2', '#8a9fed', '#2b48bd'])
    plt.title("Crater Size Distribution")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()

    return {
        "filename": filename,
        "original_image": upload_path,
        "result_image": result_path,
        "heatmap": heatmap_path,
        "riskmap": riskmap_path,
        "chart": chart_path,
        "csv": csv_path,
        "stats": stats,
        "crater_data": crater_data,
        "width": width,
        "height": height
    }
def create_combined_region_map(reports):
    num_images = len(reports)
    if num_images <= 1:
        return None
        
    cols = math.ceil(math.sqrt(num_images))
    rows = math.ceil(num_images / cols)
    
    cell_w = 640
    cell_h = 640
    
    combined_img = np.zeros((rows * cell_h, cols * cell_w, 3), dtype=np.uint8)
    
    combined_craters = []
    combined_csv_data = [["Global_ID", "Original_Image", "X_Center_Global", "Y_Center_Global", "Diameter", "Depth_Est", "Morphology", "Confidence", "Quadrant"]]
    
    global_id = 1
    total_area = 0
    size_counts = {"Small": 0, "Medium": 0, "Large": 0}

    for idx, rep in enumerate(reports):
        row = idx // cols
        col = idx % cols
        
        offset_x = col * cell_w
        offset_y = row * cell_h
        
        orig = cv2.imread(rep["original_image"])
        orig_resized = cv2.resize(orig, (cell_w, cell_h))
        combined_img[offset_y:offset_y+cell_h, offset_x:offset_x+cell_w] = orig_resized
        
        scale_x = cell_w / rep["width"]
        scale_y = cell_h / rep["height"]
        total_area += (rep["width"] * rep["height"])

        for c in rep["crater_data"]:
            gx = c["x"] * scale_x + offset_x
            gy = c["y"] * scale_y + offset_y
            gw = c["diameter"] * scale_x
            
            combined_craters.append({
                "id": global_id,
                "orig_id": c["id"],
                "gx": gx, "gy": gy, "diameter": gw
            })
            
            size_class = c.get("size", "Small")
            if size_class in size_counts:
                size_counts[size_class] += 1
            elif size_class == "small": size_counts["Small"] += 1
            elif size_class == "medium": size_counts["Medium"] += 1
            else: size_counts["Large"] += 1

            combined_csv_data.append([global_id, rep["filename"], round(gx, 2), round(gy, 2), round(gw, 2), c["depth"], c["morphology"], c["confidence"], c["quadrant"]])
            global_id += 1

    combined_map_filename = "combined_map_" + str(uuid.uuid4()) + ".jpg"
    combined_map_path = os.path.join(RESULT_FOLDER, combined_map_filename)
    
    combined_heatmap_filename = "combined_heatmap_" + str(uuid.uuid4()) + ".jpg"
    combined_heatmap_path = os.path.join(RESULT_FOLDER, combined_heatmap_filename)
    
    combined_csv_filename = "combined_dataset_" + str(uuid.uuid4()) + ".csv"
    combined_csv_path = os.path.join(DATASET_FOLDER, combined_csv_filename)
    
    map_drawn = combined_img.copy()
    heatmap = np.zeros((rows * cell_h, cols * cell_w), dtype=np.float32)
    
    for c in combined_craters:
        cv2.circle(map_drawn, (int(c["gx"]), int(c["gy"])), 2, (0, 0, 255), -1)
        cv2.circle(map_drawn, (int(c["gx"]), int(c["gy"])), int(c["diameter"]/2), (0, 255, 0), 2)
        cv2.circle(heatmap, (int(c["gx"]), int(c["gy"])), int(c["diameter"]/2), 1, -1)
        
    cv2.imwrite(combined_map_path, map_drawn)
    
    heatmap = cv2.GaussianBlur(heatmap, (51, 51), 0)
    heatmap_norm = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    
    # Combined Heatmap
    heatmap_color = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_JET)
    combined_heatmap_img = cv2.addWeighted(combined_img, 0.5, heatmap_color, 0.5, 0)
    cv2.imwrite(combined_heatmap_path, combined_heatmap_img)
    
    # Combined Risk Map
    combined_riskmap_filename = "combined_riskmap_" + str(uuid.uuid4()) + ".jpg"
    combined_riskmap_path = os.path.join(RESULT_FOLDER, combined_riskmap_filename)
    
    advanced_combined_riskmap = generate_advanced_safety_map(combined_img, combined_craters, tile_size=128)
    if advanced_combined_riskmap is not None:
        cv2.imwrite(combined_riskmap_path, advanced_combined_riskmap)
    else:
        risk_color = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_AUTUMN)
        cv2.imwrite(combined_riskmap_path, cv2.addWeighted(combined_img, 0.4, risk_color, 0.6, 0))

    with open(combined_csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(combined_csv_data)
        
    regional_chart_filename = "combined_chart_" + str(uuid.uuid4()) + ".jpg"
    regional_chart_path = os.path.join(RESULT_FOLDER, regional_chart_filename)
    
    plt.figure(figsize=(6, 4))
    sizes = [size_counts["Small"], size_counts["Medium"], size_counts["Large"]]
    labels = ["Small", "Medium", "Large"]
    plt.bar(labels, sizes, color=['#4e6ef2', '#8a9fed', '#2b48bd'])
    plt.title("Regional Crater Size Distribution")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(regional_chart_path)
    plt.close()

    regional_density = round((len(combined_craters) / total_area) * 1000000, 2) if total_area > 0 else 0
        
    return {
        "map_image": combined_map_path,
        "heatmap_image": combined_heatmap_path,
        "csv": combined_csv_path,
        "total_craters": len(combined_craters),
        "regional_density": regional_density,
        "size_counts": size_counts,
        "chart": regional_chart_path,
        "riskmap": combined_riskmap_path
    }

@app.route("/", methods=["GET", "POST"])
def index():
    images = []
    if os.path.exists(RESULT_FOLDER):
        images = [f for f in os.listdir(RESULT_FOLDER) if (f.endswith(".jpg") or f.endswith(".png")) and not any(f.startswith(prefix) for prefix in ["heatmap_", "riskmap_", "chart_", "combined_"])]

    if request.method == "POST":
        files = request.files.getlist("image")
        reports = []
        global_summary = { "images": 0, "total_craters": 0, "avg_density": 0 }
        
        for file in files:
            if file and file.filename != '' and allowed_file(file.filename):
                filename = str(uuid.uuid4()) + ".jpg"
                upload_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(upload_path)
                rep = process_image(upload_path, filename)
                reports.append(rep)
                
                global_summary["images"] += 1
                global_summary["total_craters"] += rep["stats"]["total"]
                global_summary["avg_density"] += rep["stats"]["density"]
                
        if global_summary["images"] > 0:
            global_summary["avg_density"] = round(global_summary["avg_density"] / global_summary["images"], 2)
            
        combined_region = create_combined_region_map(reports)
            
        images = [os.path.basename(rep["result_image"]) for rep in reports]
            
        return render_template("index.html", uploaded=True, reports=reports, summary=global_summary, combined_region=combined_region, images=images)

    return render_template("index.html", uploaded=False, images=images)

if __name__ == "__main__":
    app.run(debug=True)