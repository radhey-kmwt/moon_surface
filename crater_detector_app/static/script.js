document.addEventListener('DOMContentLoaded', () => {
    // 1. Starfield generation using Canvas
    const canvas = document.createElement('canvas');
    canvas.id = 'starfield';
    canvas.style.position = 'fixed';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.zIndex = '-1';
    canvas.style.pointerEvents = 'none';
    document.body.prepend(canvas);

    const ctx = canvas.getContext('2d');
    let width, height;
    let stars = [];
    
    // Parallax variables
    let mouseX = window.innerWidth / 2;
    let mouseY = window.innerHeight / 2;
    let targetMouseX = 0;
    let targetMouseY = 0;

    document.addEventListener('mousemove', (e) => {
        targetMouseX = (e.clientX - width / 2) * 0.05;
        targetMouseY = (e.clientY - height / 2) * 0.05;
    });

    function initCanvas() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    }

    class Star {
        constructor() {
            this.x = Math.random() * width;
            this.y = Math.random() * height;
            // z determines the speed and size to simulate depth
            this.z = Math.random() * 2; 
            this.size = Math.random() * 1.5;
            this.alpha = Math.random();
            this.velocity = (Math.random() * 0.05 + 0.05) * (this.z + 1);
        }
        update() {
            this.y -= this.velocity;
            
            // Twinkling effect
            this.alpha += (Math.random() - 0.5) * 0.05;
            if (this.alpha < 0.1) this.alpha = 0.1;
            if (this.alpha > 0.8) this.alpha = 0.8;

            // Reset star to bottom when it reaches the top
            if (this.y < 0) {
                this.y = height;
                this.x = Math.random() * width;
            }
        }
        draw(offsetX, offsetY) {
            ctx.fillStyle = `rgba(255, 255, 255, ${this.alpha})`;
            ctx.beginPath();
            // Apply parallax offset scaled by z-depth (larger stars move more)
            const px = this.x + offsetX * (this.z * 1.5 + 1);
            const py = this.y + offsetY * (this.z * 1.5 + 1);
            
            // Allow wrapping for seamless parallax
            let drawX = px;
            let drawY = py;
            
            // Adjust bounds based on offset to keep stars flowing
            if (drawX < -100) drawX = width + (drawX % width);
            if (drawX > width + 100) drawX = (drawX % width);
            
            ctx.arc(drawX, drawY, this.size, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    function createStars() {
        stars = [];
        // Calculate number of stars based on screen size
        const numStars = Math.floor(width * height / 2500); 
        for (let i = 0; i < numStars; i++) {
            stars.push(new Star());
        }
    }

    function animate() {
        ctx.clearRect(0, 0, width, height);
        
        // Smoothly interpolate current mouse offset towards target
        const offsetSpeed = 0.05;
        mouseX += (targetMouseX - mouseX) * offsetSpeed;
        mouseY += (targetMouseY - mouseY) * offsetSpeed;

        stars.forEach(star => {
            star.update();
            star.draw(mouseX, mouseY);
        });
        requestAnimationFrame(animate);
    }

    window.addEventListener('resize', () => {
        initCanvas();
        createStars();
    });

    // Initialize animation
    initCanvas();
    createStars();
    animate();

    // 2. UI Interactions (Drag and drop, file selection, loading state)
    const fileInput = document.getElementById('image-upload');
    const fileNameDisplay = document.getElementById('file-name');
    const uploadArea = document.getElementById('upload-area');
    const form = document.getElementById('upload-form');
    const submitBtn = document.getElementById('submit-btn');
    const loadingIndicator = document.getElementById('loading-indicator');

    if (fileInput) {
        // Update file name display and show image preview when native dialog is used
        fileInput.addEventListener('change', function() {
            if (this.files && this.files.length > 0) {
                if (this.files.length === 1) {
                    fileNameDisplay.textContent = 'Selected: ' + this.files[0].name;
                } else {
                    fileNameDisplay.textContent = 'Selected ' + this.files.length + ' lunar region images.';
                }
                submitBtn.disabled = false;
                
                const previewImg = document.getElementById('preview-img');
                if (previewImg) previewImg.remove();
                
                // Show preview of first image if there is one
                if (this.files.length === 1) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        let newPreview = document.createElement('img');
                        newPreview.id = 'preview-img';
                        newPreview.style.maxWidth = '100%';
                        newPreview.style.maxHeight = '200px';
                        newPreview.style.marginTop = '15px';
                        newPreview.style.borderRadius = '8px';
                        newPreview.style.boxShadow = '0 4px 15px rgba(0,0,0,0.5)';
                        newPreview.src = e.target.result;
                        fileNameDisplay.parentNode.insertBefore(newPreview, fileNameDisplay.nextSibling);
                        
                        const icon = document.querySelector('.upload-icon');
                        if(icon) icon.style.display = 'none';
                    }
                    reader.readAsDataURL(this.files[0]);
                } else {
                    const icon = document.querySelector('.upload-icon');
                    if(icon) icon.style.display = 'block';
                }
            } else {
                fileNameDisplay.textContent = '';
                submitBtn.disabled = true;
                
                const previewImg = document.getElementById('preview-img');
                if (previewImg) previewImg.remove();
                
                const icon = document.querySelector('.upload-icon');
                if(icon) icon.style.display = 'block';
            }
        });

        // Trigger file select dialog on clicking upload area
        uploadArea.addEventListener('click', () => {
            fileInput.click();
        });

        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, preventDefaults, false);
            document.body.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        // Highlight upload area on hover or dragover
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, unhighlight, false);
        });

        function highlight() {
            uploadArea.classList.add('dragover');
        }

        function unhighlight() {
            uploadArea.classList.remove('dragover');
        }

        // Handle physical file drop
        uploadArea.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            let dt = e.dataTransfer;
            let files = dt.files;

            if (files && files.length > 0) {
                if (files[0].type.startsWith('image/')) {
                    fileInput.files = files; // transfer dropped files to the input field
                    // manually trigger change event
                    const event = new Event('change');
                    fileInput.dispatchEvent(event);
                } else {
                    alert('Please upload an image file.');
                }
            }
        }
    }

    if (form) {
        // Handle form submission to show loading indicator
        form.addEventListener('submit', function(e) {
            if (!fileInput.files || fileInput.files.length === 0) {
                e.preventDefault();
                alert("Please select a lunar image first.");
                return;
            }

            // Hide upload section to clean up UI
            uploadArea.style.pointerEvents = 'none';
            uploadArea.style.opacity = '0.5';
            
            // Show loading spinner and swap button
            submitBtn.style.display = 'none';
            loadingIndicator.style.display = 'block';
            
            // Initiate Typewriter Effect for loading text
            const loadingText = document.getElementById('loading-text');
            if (loadingText) {
                const textToType = "Analyzing lunar surface scan data... Please wait.";
                loadingText.textContent = "";
                let i = 0;
                loadingText.classList.add('typing-cursor');
                
                const typeWriter = setInterval(() => {
                    if (i < textToType.length) {
                        loadingText.textContent += textToType.charAt(i);
                        i++;
                    } else {
                        clearInterval(typeWriter);
                        // Optional: remove cursor or blink it differently when done
                    }
                }, 45); // Adjust speed here
            }
        });
    }

    // Apply crater tooltip dynamic positioning
    const tooltips = document.querySelectorAll('.crater-tooltip-target');
    tooltips.forEach(tooltip => {
        if (tooltip.dataset.left) tooltip.style.left = tooltip.dataset.left + '%';
        if (tooltip.dataset.top) tooltip.style.top = tooltip.dataset.top + '%';
        if (tooltip.dataset.width) tooltip.style.width = tooltip.dataset.width + '%';
        if (tooltip.dataset.height) tooltip.style.height = tooltip.dataset.height + '%';
    });

    // Handle Tabs interactions
    const tabMenus = document.querySelectorAll('.tabs-header');
    tabMenus.forEach(menu => {
        const btns = menu.querySelectorAll('.tab-btn');
        btns.forEach(btn => {
            btn.addEventListener('click', () => {
                // Remove active from all btns in this menu
                btns.forEach(b => b.classList.remove('active'));
                
                // Find all tab contents related to this report
                const parentSection = menu.closest('.results-section');
                const contents = parentSection.querySelectorAll('.tab-content');
                contents.forEach(c => c.classList.remove('active'));
                
                // Add active to the clicked btn & target content
                btn.classList.add('active');
                const targetId = btn.getAttribute('data-target');
                const targetContent = document.getElementById(targetId);
                if(targetContent) targetContent.classList.add('active');
            });
        });
    });
});

// Global function to handle page switching
window.switchPage = function(pageId, event) {
    if(event) {
        event.preventDefault();
    }
    
    // Remove active class from all pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    
    // Remove active class from all nav links
    document.querySelectorAll('.nav-link').forEach(btn => btn.classList.remove('active'));
    
    // Add active class to target page
    const targetPage = document.getElementById('page-' + pageId);
    if(targetPage) {
        targetPage.classList.add('active');
    }
    
    // Add active class to clicked button
    if(event && event.currentTarget) {
        event.currentTarget.classList.add('active');
    } else {
        // Fallback to finding the button by onclick attribute if event isn't passed perfectly
        const btn = document.querySelector(`.nav-link[onclick*="${pageId}"]`);
        if(btn) btn.classList.add('active');
    }
};
