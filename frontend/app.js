const video = document.getElementById('webcam');
const canvas = document.getElementById('output');
const ctx = canvas.getContext('2d');
const statusElement = document.getElementById('status');
const debugElement = document.getElementById('debug');

let model = null;
let appliedColor = null;
let isModelLoaded = false;

// Correct MediaPipe Face Mesh lip landmark indices
const LIP_UPPER_OUTER = [61, 84, 17, 314, 405, 320, 307, 375, 321, 308, 324, 318];
const LIP_LOWER_OUTER = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 415];
const LIP_UPPER_INNER = [78, 81, 80, 82, 13, 312, 311, 310, 415, 95];
const LIP_LOWER_INNER = [88, 178, 87, 14, 317, 402, 318, 324];

// Combined lip contour for better coverage
const FULL_LIP_CONTOUR = [
    // Upper outer lip
    61, 84, 17, 314, 405, 320, 307, 375, 321, 308,
    // Right corner to lower lip
    324, 318, 402, 317, 14, 87, 178, 88, 95,
    // Lower lip back to start
    78, 191, 80, 81, 82, 13, 312, 311, 310, 415
];

// Setup webcam
async function setupWebcam() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: 640,
                height: 480,
                facingMode: 'user'
            }
        });
        video.srcObject = stream;

        return new Promise((resolve) => {
            video.onloadedmetadata = () => {
                video.play();
                resolve(video);
            };
        });
    } catch (error) {
        console.error('Error accessing webcam:', error);
        statusElement.textContent = 'Error accessing camera. Please allow camera permissions.';
        throw error;
    }
}

// Load face landmarks model
async function loadModel() {
    try {
        statusElement.textContent = 'Loading face detection model...';

        model = await faceLandmarksDetection.createDetector(
            faceLandmarksDetection.SupportedModels.MediaPipeFaceMesh,
            {
                runtime: 'tfjs',
                refineLandmarks: true,
                maxFaces: 1
            }
        );

        isModelLoaded = true;
        statusElement.textContent = 'Model loaded! Click a color or use Apply button.';
        console.log("Face landmarks model loaded successfully");

    } catch (error) {
        console.error('Error loading model:', error);
        statusElement.textContent = 'Error loading model. Please refresh the page.';
        throw error;
    }
}

// Convert hex color to RGB
function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16)
    } : null;
}

// Draw lips with color overlay
function drawLips(predictions) {
    if (!appliedColor || !predictions.length) return;

    const face = predictions[0];
    const keypoints = face.keypoints;
    if (!keypoints || keypoints.length < 468) return;

    const rgb = hexToRgb(appliedColor);
    if (!rgb) return;

    ctx.save();
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 0.7;

    ctx.beginPath();
    // Outer lip
    const outer = LIP_UPPER_OUTER.concat(LIP_LOWER_OUTER).map(i => keypoints[i]);
    ctx.moveTo(outer[0].x, outer[0].y);
    outer.forEach(p => ctx.lineTo(p.x, p.y));
    ctx.closePath();

    // Inner lip (cut out)
    const inner = LIP_UPPER_INNER.concat(LIP_LOWER_INNER).map(i => keypoints[i]);
    ctx.moveTo(inner[0].x, inner[0].y);
    inner.forEach(p => ctx.lineTo(p.x, p.y));
    ctx.closePath();

    // Use even-odd rule → fill only lips, not mouth cavity
    ctx.fillStyle = `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.7)`;
    ctx.fill("evenodd");

    ctx.restore();
}


// Main detection and rendering loop
async function detectAndRender() {
    if (!isModelLoaded || !model) {
        requestAnimationFrame(detectAndRender);
        return;
    }

    try {
        // Draw video frame
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        // Detect faces
        const predictions = await model.estimateFaces(video, {
            flipHorizontal: false,
            staticImageMode: false
        });

        // Apply lipstick if color is selected
        if (predictions && predictions.length > 0) {
            drawLips(predictions);
        } else if (appliedColor) {
            debugElement.textContent = 'No face detected';
        }

    } catch (error) {
        console.error('Detection error:', error);
        debugElement.textContent = `Error: ${error.message}`;
    }

    requestAnimationFrame(detectAndRender);
}

// Event listeners
document.getElementById('applyButton').addEventListener('click', () => {
    appliedColor = document.getElementById('shadeColor').value;
    statusElement.textContent = `Lipstick applied: ${appliedColor}`;
});

document.getElementById('removeButton').addEventListener('click', () => {
    appliedColor = null;
    statusElement.textContent = 'Lipstick removed';
    debugElement.textContent = '';
});

// Preset color selection
document.querySelectorAll('.preset-color').forEach(element => {
    element.addEventListener('click', () => {
        const color = element.dataset.color;
        document.getElementById('shadeColor').value = color;
        appliedColor = color;
        statusElement.textContent = `Lipstick applied: ${color}`;
    });
});

// Color picker change
document.getElementById('shadeColor').addEventListener('change', (e) => {
    appliedColor = e.target.value;
    statusElement.textContent = `Lipstick applied: ${appliedColor}`;
});

// Initialize application
async function init() {
    try {
        statusElement.textContent = 'Initializing camera...';
        await setupWebcam();

        statusElement.textContent = 'Loading AI model...';
        await loadModel();

        // Start the detection loop
        detectAndRender();

    } catch (error) {
        console.error('Initialization error:', error);
        statusElement.textContent = 'Initialization failed. Please check console for details.';
    }
}

// Start the application when page loads
window.addEventListener('load', init);