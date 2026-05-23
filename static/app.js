let videos = [];
let activeVideoId = null;
let masterRatio = 16/9; // Default

// DOM Elements
const videoUpload = document.getElementById('videoUpload');
const videoListEl = document.getElementById('videoList');
const videoCountEl = document.getElementById('videoCount');
const loadingOverlay = document.getElementById('loadingOverlay');

const previewPlayer = document.getElementById('previewPlayer');
const placeholderPreview = document.getElementById('placeholderPreview');
const previewContainer = document.querySelector('.preview-container');

const clipSettingsPanel = document.getElementById('clipSettingsPanel');
const btnRotLeft = document.getElementById('btnRotLeft');
const btnRotRight = document.getElementById('btnRotRight');
const btnRot180 = document.getElementById('btnRot180');
const btnRotReset = document.getElementById('btnRotReset');

const btnFit = document.getElementById('btnFit');
const btnFill = document.getElementById('btnFill');
const clipRatioSelect = document.getElementById('clipRatioSelect');

const exportFormat = document.getElementById('exportFormat');
const exportResolution = document.getElementById('exportResolution');
const exportQuality = document.getElementById('exportQuality');
const crfValue = document.getElementById('crfValue');
const outputFolderPath = document.getElementById('outputFolderPath');
const btnPickFolder = document.getElementById('btnPickFolder');
const btnExport = document.getElementById('btnExport');

const exportProgressContainer = document.getElementById('exportProgressContainer');
const progressBarFill = document.getElementById('progressBarFill');
const progressStatus = document.getElementById('progressStatus');
const progressPercent = document.getElementById('progressPercent');

// Events
videoUpload.addEventListener('change', handleUpload);
exportQuality.addEventListener('input', (e) => crfValue.textContent = e.target.value);
btnPickFolder.addEventListener('click', handlePickFolder);
btnExport.addEventListener('click', handleExport);

// Clip Settings Events
btnRotLeft.addEventListener('click', () => updateActiveClip('rotate', (getValidRotation(-90))));
btnRotRight.addEventListener('click', () => updateActiveClip('rotate', (getValidRotation(90))));
btnRot180.addEventListener('click', () => updateActiveClip('rotate', (getValidRotation(180))));
btnRotReset.addEventListener('click', () => updateActiveClip('rotate', 0));

btnFit.addEventListener('click', () => {
    btnFit.classList.add('active');
    btnFill.classList.remove('active');
    updateActiveClip('fitFill', 'fit');
});
btnFill.addEventListener('click', () => {
    btnFill.classList.add('active');
    btnFit.classList.remove('active');
    updateActiveClip('fitFill', 'fill');
});

clipRatioSelect.addEventListener('change', (e) => updateActiveClip('ratio', e.target.value));

function getValidRotation(degAdd) {
    if(!activeVideoId) return 0;
    const v = videos.find(v => v.id === activeVideoId);
    let rot = (v.rotate || 0) + degAdd;
    rot = rot % 360;
    if (rot === -270) rot = 90;
    if (rot === 270) rot = -90;
    return rot;
}

async function handleUpload(e) {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    loadingOverlay.style.display = 'flex';

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            
            if (data.error) {
                console.error(data.error);
                continue;
            }

            const videoObj = {
                id: 'v_' + Math.random().toString(36).substr(2, 9),
                filename: data.filename,
                width: data.width,
                height: data.height,
                duration: data.duration,
                url: data.url,
                thumbnail: data.thumbnail,
                rotate: 0,
                fitFill: 'fit',
                ratio: 'Original'
            };

            videos.push(videoObj);

            // If first video, set master ratio
            if (videos.length === 1) {
                masterRatio = videoObj.width / videoObj.height;
                previewContainer.style.aspectRatio = `${videoObj.width}/${videoObj.height}`;
            }

        } catch (err) {
            console.error("Upload failed", err);
        }
    }

    loadingOverlay.style.display = 'none';
    videoUpload.value = ''; // Reset input
    renderVideoList();
    
    // Auto select first if none selected
    if (videos.length > 0 && !activeVideoId) {
        selectVideo(videos[0].id);
    }
}

function renderVideoList() {
    videoListEl.innerHTML = '';
    videoCountEl.textContent = videos.length;

    videos.forEach((v, index) => {
        const card = document.createElement('div');
        card.className = `video-card ${v.id === activeVideoId ? 'active' : ''}`;
        card.draggable = true;
        card.dataset.id = v.id;

        card.innerHTML = `
            <img src="${v.thumbnail}" class="video-thumb" alt="thumb">
            <div class="video-info">
                <div class="video-title" title="${v.filename}">${v.filename}</div>
                <div class="video-meta">${v.width}x${v.height} • ${v.duration.toFixed(1)}s</div>
            </div>
            <button class="delete-btn" onclick="event.stopPropagation(); removeVideo('${v.id}')">✕</button>
        `;

        card.addEventListener('click', () => selectVideo(v.id));
        
        // Drag events
        card.addEventListener('dragstart', handleDragStart);
        card.addEventListener('dragover', handleDragOver);
        card.addEventListener('drop', handleDrop);
        card.addEventListener('dragenter', handleDragEnter);
        card.addEventListener('dragleave', handleDragLeave);

        videoListEl.appendChild(card);
    });
}

function selectVideo(id) {
    activeVideoId = id;
    renderVideoList(); // Update active class
    
    const v = videos.find(v => v.id === id);
    if (!v) return;

    // Update settings panel UI
    clipSettingsPanel.style.display = 'block';
    if(v.fitFill === 'fit') {
        btnFit.classList.add('active'); btnFill.classList.remove('active');
    } else {
        btnFill.classList.add('active'); btnFit.classList.remove('active');
    }
    clipRatioSelect.value = v.ratio || 'Original';

    // Update preview player
    placeholderPreview.style.display = 'none';
    previewPlayer.style.display = 'block';
    
    // Only reload source if it's a different video to prevent flicker
    if(!previewPlayer.src.includes(v.url)) {
        previewPlayer.src = v.url;
        previewPlayer.play().catch(e => console.log("Auto-play prevented", e));
    }
    
    applyPreviewTransforms();
}

function updateActiveClip(key, value) {
    if (!activeVideoId) return;
    const v = videos.find(v => v.id === activeVideoId);
    if (v) {
        v[key] = value;
        applyPreviewTransforms();
    }
}

function applyPreviewTransforms() {
    if (!activeVideoId) return;
    const v = videos.find(v => v.id === activeVideoId);
    
    // We simulate the ffmpeg transforms using CSS
    let transformStr = `rotate(${v.rotate}deg)`;
    let objFit = v.fitFill === 'fit' ? 'contain' : 'cover';

    previewPlayer.style.transform = transformStr;
    previewPlayer.style.objectFit = objFit;

    // Simulate ratio
    // If ratio is not Original, we can force the player's aspect ratio
    // This is a rough approximation for the preview
    if(v.ratio !== 'Original') {
        const ratioParts = v.ratio.split(':');
        previewPlayer.style.aspectRatio = `${ratioParts[0]}/${ratioParts[1]}`;
        previewPlayer.style.width = '100%';
        previewPlayer.style.height = '100%';
    } else {
        previewPlayer.style.aspectRatio = 'auto';
        previewPlayer.style.width = '100%';
        previewPlayer.style.height = '100%';
    }
}

function removeVideo(id) {
    videos = videos.filter(v => v.id !== id);
    if (activeVideoId === id) {
        activeVideoId = videos.length > 0 ? videos[0].id : null;
        if (!activeVideoId) {
            clipSettingsPanel.style.display = 'none';
            previewPlayer.style.display = 'none';
            placeholderPreview.style.display = 'block';
            previewPlayer.pause();
            previewPlayer.src = '';
        } else {
            selectVideo(activeVideoId);
        }
    }
    renderVideoList();
}

// --- Drag and Drop Logic ---
let draggedElement = null;

function handleDragStart(e) {
    draggedElement = this;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', this.dataset.id);
    setTimeout(() => this.classList.add('dragging'), 0);
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDragEnter(e) {
    e.preventDefault();
    this.style.borderTop = '2px solid var(--accent-color)';
}

function handleDragLeave(e) {
    this.style.borderTop = '';
}

function handleDrop(e) {
    e.stopPropagation();
    this.style.borderTop = '';
    
    if (draggedElement !== this) {
        const draggedId = e.dataTransfer.getData('text/plain');
        const targetId = this.dataset.id;
        
        const draggedIndex = videos.findIndex(v => v.id === draggedId);
        const targetIndex = videos.findIndex(v => v.id === targetId);
        
        // Reorder array
        const [movedItem] = videos.splice(draggedIndex, 1);
        videos.splice(targetIndex, 0, movedItem);
        
        renderVideoList();
    }
    return false;
}
document.addEventListener('dragend', () => {
    if(draggedElement) draggedElement.classList.remove('dragging');
    document.querySelectorAll('.video-card').forEach(c => c.style.borderTop = '');
});

// --- Export & Settings ---
async function handlePickFolder() {
    try {
        const res = await fetch('/pick-folder');
        const data = await res.json();
        if (data.path) {
            outputFolderPath.value = data.path;
        } else if (data.error) {
            console.error(data.error);
        }
    } catch (e) {
        console.error(e);
    }
}

let ws = null;

async function handleExport() {
    if (videos.length === 0) {
        alert("Please add some videos first.");
        return;
    }
    if (!outputFolderPath.value) {
        alert("Please select an output folder.");
        return;
    }

    // Connect WS if not connected
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        ws = new WebSocket(`ws://${window.location.host}/ws/progress`);
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if(data.status === 'processing') {
                progressPercent.textContent = `${data.progress}%`;
                progressBarFill.style.width = `${data.progress}%`;
                progressStatus.textContent = "Merging...";
            } else if (data.status === 'completed') {
                progressPercent.textContent = `100%`;
                progressBarFill.style.width = `100%`;
                progressStatus.textContent = "Completed Successfully!";
                btnExport.disabled = false;
                btnExport.textContent = "Export Video";
                btnExport.classList.add('pulse');
            } else if (data.status === 'error') {
                progressStatus.textContent = "Error: " + data.message;
                progressBarFill.style.background = "var(--danger-color)";
                btnExport.disabled = false;
                btnExport.textContent = "Export Video";
            }
        };
    }

    exportProgressContainer.style.display = 'block';
    progressBarFill.style.width = '0%';
    progressPercent.textContent = '0%';
    progressStatus.textContent = 'Starting...';
    btnExport.disabled = true;
    btnExport.textContent = "Processing...";
    btnExport.classList.remove('pulse');

    const payload = {
        videos: videos,
        output_path: outputFolderPath.value,
        format: exportFormat.value,
        resolution: exportResolution.value,
        quality: parseInt(exportQuality.value),
        master_ratio: masterRatio
    };

    try {
        const res = await fetch('/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if(data.error) {
            alert(data.error);
            btnExport.disabled = false;
            btnExport.textContent = "Export Video";
        }
    } catch (e) {
        console.error(e);
        alert("Export request failed.");
        btnExport.disabled = false;
        btnExport.textContent = "Export Video";
    }
}
