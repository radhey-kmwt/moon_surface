# AI-Powered Lunar Crater Detector App
An advanced, browser-based Machine Learning pipeline for the autonomous detection, classification, and analysis of lunar terrain craters built on YOLO neural networks and Flask. This project dynamically maps safe landing zones for spacecraft by automatically analyzing surface deformation, terrain ruggedness, crater size distribution, and overlapping regions from satellite imagery.

## Features
- **YOLO Deep Learning Pipeline:** Employs an optimized YOLO model to map boundaries and structural measurements of individual craters across arbitrary resolution satellite maps.
- **Dynamic Terrain Dashboard:** Rich dashboard displaying real-time metrics including average crater density, morphological stats, intersection over union (IoU) overlaps, and estimated baseline ages (Copernican vs. Imbrian).
- **Data Extractor:** Exports bounding box metrics, coordinates, confidence scores, and crater depths to a structured dataset (CSV format) for researchers.
- **Continuous Regional Context:** Allows bulk-uploading of multiple spatial imaging tiles to algorithmically stitch bounding measurements and form large-scale cohesive Lunar Maps without duplicate tracking over bounds.
- **Landing Safety Analyzer:** Uses bounding parameters coupled to pixel-intensity roughness heuristics to visually classify grids into abort-zones (red) vs viable smooth surface green zones. 

## Requirements
To execute this analysis pipeline, install the following dependencies:
- Python 3.9+
- Flask (`pip install flask`)
- Ultralytics / YOLO (`pip install ultralytics`)
- OpenCV (`pip install opencv-python`)
- NumPy & Matplotlib (`pip install numpy matplotlib`)

## Installation & Setup
1. Clone or download the repository to your local system.
2. Open a terminal and navigate to the project root directory.
3. Place your valid Ultralytics YOLO trained weights file at `model/best.pt`.
4. Install all prerequisites using pip.
5. Launch the backend application environment:
   `python app.py`
6. Navigate to `http://localhost:5000` from your browser to open the mission dashboard.

## Usage
1. Open the application and stay on the **1. Satellite Image Upload** tab.
2. Select or drag & drop one or multiple (`.jpg`/`.png`) lunar surface captures onto the drop-zone.
3. Click **Initiate Neural Network** to pass the tensors forward to the YOLO back-end. 
4. The system will process each image and automatically route you to the AI interpretation feeds. Wait for the computation to finish.
5. Use the navigation bar to tab across raw detection feeds, density heatmaps, safety zones, and regional stitches.

## Tech Stack
- **Backend:** Flask, Python
- **ML / Vision:** Ultralytics YOLO, OpenCV, Matplotlib
- **Frontend / Styling:** Vanilla HTML5, CSS3, Javascript (Custom space-themed web-aesthetics with glassmorphism).
