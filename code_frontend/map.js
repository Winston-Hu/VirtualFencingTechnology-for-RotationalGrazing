// Leaflet Initialization
const leafletMap = L.map('map').setView([-33.919125, 151.229565], 15);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap'
}).addTo(leafletMap);

// Add virtual fence on map
function addVirtualFence(name, polygonCoords) {
    const polygon = L.polygon(polygonCoords).addTo(leafletMap).bindTooltip(name);
    const center = polygon.getBounds().getCenter();

    const marker = L.marker(center, {
        icon: L.icon({
            iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41]
        })
    }).addTo(leafletMap).bindTooltip(name);

    // Hide marker by default
    marker.setOpacity(0);

    function updateVisibility() {
        const zoom = leafletMap.getZoom();
        if (zoom < 18) {
            leafletMap.removeLayer(polygon);
            marker.setOpacity(1);
        } else {
            polygon.addTo(leafletMap);
            marker.setOpacity(0);
        }
    }
    leafletMap.on('zoomend', updateVisibility);
    updateVisibility();

    marker.on('click', () => leafletMap.fitBounds(polygon.getBounds()));

    polygon.on('click', () => {
        document.getElementById('overlayCanvas').style.display = 'block';
        drawField();
    });
}

// Fence coordinates
addVirtualFence('Test Field', [
    [-33.91909027708148, 151.2296022312546],
    [-33.91919156541506, 151.22960004474643],
    [-33.91921037153495, 151.22985535030368],
    [-33.91910253475983, 151.22985535030368]
]);

// Close Canvas button
document.getElementById('closeCanvasBtn').addEventListener('click', () => {
    document.getElementById('overlayCanvas').style.display = 'none';
});

// Global cache
const cowDots = [];
let listenersBound = false;
let activeCow = null;

// Inner fence coordinate conversion
function getInnerFenceCoordinates(gridX, gridY) {
    const cell = 75;
    const offsetX = 180;
    const offsetY = 30;

    const ox = x => offsetX + (x + 2) / 2 * cell;
    const oy = y => offsetY + (y + 2) / 2 * cell;

    const minXp = ox(-2);
    const maxXp = ox(10);
    const minYp = oy(-2);
    const maxYp = oy(18);
    const rotW = maxYp - minYp;
    const rotH = maxXp - minXp;

    const canvas = document.getElementById('canvas');
    const baseX = (canvas.width - rotW) / 2;
    const baseY = (canvas.height - rotH) / 2;

    // Rotation function
    const rot = (xp, yp) => [baseX + (yp - minYp), baseY + (maxXp - xp)];
    const greenOffsetY = -cell;
    const [rx0, ry0] = rot(ox(gridY) - cell / 2, oy(gridX) - cell / 2);

    // Center the cow in the square
    const rotX = rx0 + cell / 2;
    const rotY = ry0 + greenOffsetY + cell / 2;

    return [rotX, rotY];
}

// Outer fence coordinate conversion
function getOuterFenceCoordinates(gridX, gridY) {
    const cell = 75;
    const offsetX = 180;
    const offsetY = 30;

    // Handle -3 coordinates properly for cow positioning
    const adjustedX = gridX === -3 ? -2 : gridX;

    const ox = x => offsetX + (x + 2) / 2 * cell;
    const oy = y => offsetY + (y + 2) / 2 * cell;

    const minXp = ox(-2);
    const maxXp = ox(10);
    const minYp = oy(-2);
    const maxYp = oy(18);
    const rotW = maxYp - minYp;
    const rotH = maxXp - minXp;

    const canvas = document.getElementById('canvas');
    const baseX = (canvas.width - rotW) / 2;
    const baseY = (canvas.height - rotH) / 2;

    // For outer fence, use the same positioning as red dots
    const pixelX = ox(adjustedX);
    const pixelY = oy(gridY);

    // Apply rotation conversion
    const rot = (xp, yp) => [baseX + (yp - minYp), baseY + (maxXp - xp)];
    return rot(pixelX, pixelY);
}

function drawField(showPanel = false) {
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // grid pixel conversion
    const cell = 75;
    const offsetX = 180;
    const offsetY = 30;
    const cols = [-2, 0, 2, 4, 6, 8, 10];
    const rows = [-2, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18];
    const ox = x => offsetX + (x + 2) / 2 * cell;
    const oy = y => offsetY + (y + 2) / 2 * cell;

    // pixel boundaries
    const minXp = ox(cols[0]);
    const maxXp = ox(cols.at(-1));
    const minYp = oy(rows[0]);
    const maxYp = oy(rows.at(-1));
    const rotW = maxYp - minYp;
    const rotH = maxXp - minXp;
    const baseX = (canvas.width - rotW) / 2;
    const baseY = (canvas.height - rotH) / 2;
    const rot = (xp, yp) => [baseX + (yp - minYp), baseY + (maxXp - xp)];

    // Outer grid
    ctx.strokeStyle = '#555';
    ctx.lineWidth = 1;
    cols.forEach(x => {
        const [x0, y0] = rot(ox(x), oy(rows[0]));
        const [x1, y1] = rot(ox(x), oy(rows.at(-1)));
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.stroke();
    });
    rows.forEach(y => {
        const [x0, y0] = rot(ox(cols[0]), oy(y));
        const [x1, y1] = rot(ox(cols.at(-1)), oy(y));
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.stroke();
    });

    // Inner coordinates (green)
    const greenOffsetY = -cell; // Move up one cell
    for (let gx = 1; gx <= 7; gx += 2) {
        for (let gy = 1; gy <= 15; gy += 2) {
            const [rx0, ry0] = rot(ox(gx) - cell / 2, oy(gy) - cell / 2);
            const rx = rx0;
            const ry = ry0 + greenOffsetY;
            ctx.fillStyle = 'rgba(102,204,51,0.4)';
            ctx.fillRect(rx, ry, cell, cell);

            ctx.fillStyle = '#fff';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${gy}_${gx}`, rx + cell / 2, ry + cell / 2);
        }
    }

    // Draw all cow dots, excluding collar-dropped cows
    cowDots.forEach(cow => {
        // Only draw non-collar-dropped cows (coordinates not [-99,-99])
        if (!(cow.gridPos[0] === -99 && cow.gridPos[1] === -99)) {
            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.arc(cow.x, cow.y, cow.r + 2, 0, Math.PI * 2);
            ctx.fill();

            // Draw cow dot
            ctx.fillStyle = cow.color;
            ctx.beginPath();
            ctx.arc(cow.x, cow.y, cow.r, 0, Math.PI * 2);
            ctx.fill();

            // Add cow ID label
            ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
            ctx.fillRect(cow.x - 15, cow.y + cow.r + 8, 30, 14);

            ctx.fillStyle = '#000';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(cow.id, cow.x, cow.y + cow.r + 15);
        }
    });

    // Outer coordinate points
    const redPts = [
        [-3, 0], [-3, 4], [-3, 8], [-3, 12], [-3, 16],
        [2, -2], [6, -2],
        [10, 0], [10, 4], [10, 8], [10, 12], [10, 16],
        [2, 18], [6, 18]
    ];
    ctx.fillStyle = '#800000';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    redPts.forEach(([xg, yg]) => {
        const displayX = xg;
        const displayY = yg;
        const actualX = xg === -3 ? -2 : xg;
        const actualY = yg;

        const [rx, ry] = rot(ox(actualX), oy(actualY));
        ctx.beginPath();
        ctx.arc(rx, ry, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillText(`${displayX}_${displayY}`, rx, ry + 8);
    });

    // Receivers
    const receivers = [
        { x: 0, y: 0 }, { x: 8, y: 0 },
        { x: 0, y: 8 }, { x: 8, y: 8 },
        { x: 0, y: 16 }, { x: 8, y: 16 }
    ];
    receivers.forEach(({ x: gx, y: gy }) => {
        const [rx, ry] = rot(ox(gx), oy(gy));
        const receiverWidth = 30;
        const receiverHeight = 18;

        ctx.fillStyle = '#fff';
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 2;
        ctx.fillRect(rx - receiverWidth/2, ry - receiverHeight/2, receiverWidth, receiverHeight);
        ctx.strokeRect(rx - receiverWidth/2, ry - receiverHeight/2, receiverWidth, receiverHeight);

        ctx.strokeStyle = '#2664ff';
        [6, 9, 12].forEach(r => {
            ctx.beginPath();
            ctx.arc(rx, ry - 12, r, Math.PI, 2 * Math.PI);
            ctx.stroke();
        });

        ctx.fillStyle = '#2664ff';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(`Receiver_${gy}_${gx}`, rx, ry + 10);
    });

    // Collar dropped status bar
    const collarOffCows = cowDots.filter(cow => cow.gridPos[0] === -99 && cow.gridPos[1] === -99);
    if (collarOffCows.length > 0) {
        const statusBarHeight = 20 + (collarOffCows.length * 25);
        const statusBarWidth = 180;

        // Background
        ctx.fillStyle = 'rgba(255, 200, 200, 0.95)';
        ctx.strokeStyle = '#cc0000';
        ctx.lineWidth = 2;
        ctx.fillRect(10, 10, statusBarWidth, statusBarHeight);
        ctx.strokeRect(10, 10, statusBarWidth, statusBarHeight);

        // Title
        ctx.fillStyle = '#cc0000';
        ctx.font = 'bold 14px sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        ctx.fillText('⚠️ Collar Dropped Alert', 18, 18);

        // Display dropped collar cow information
        collarOffCows.forEach((cow, index) => {
            ctx.fillStyle = '#cc0000';
            ctx.font = '12px sans-serif';
            ctx.fillText(`${cow.id}: Location Unknown`, 18, 40 + (index * 25));
        });
    }

    // Cow information panel
    if (showPanel && activeCow) {
        const panelW = 180;
        const panelH = 100;
        const panelX = canvas.width - panelW - 10;
        const panelY = 10;

        ctx.fillStyle = 'rgba(255,255,255,0.95)';
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1;
        ctx.fillRect(panelX, panelY, panelW, panelH);
        ctx.strokeRect(panelX, panelY, panelW, panelH);

        ctx.fillStyle = '#000';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        ctx.fillText(`ID: ${activeCow.id}`, panelX + 8, panelY + 8);
        ctx.fillText(`Grid: [${activeCow.gridPos[0]}, ${activeCow.gridPos[1]}]`, panelX + 8, panelY + 28);
        ctx.fillText(`Status: ${activeCow.status === 0 ? 'Safe (Inner)' : 'Escaped (Outer)'}`, panelX + 8, panelY + 48);
    }

    // Bind hover for the first time
    if (!listenersBound) {
        bindHover(canvas);
        listenersBound = true;
    }
}

// Hover interaction
function bindHover(canvas) {
    canvas.addEventListener('mousemove', e => {
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;

        activeCow = null;
        for (const cow of cowDots) {
            if (Math.hypot(mx - cow.x, my - cow.y) <= cow.r + 3) {
                activeCow = cow;
                break;
            }
        }
        // Redraw and decide whether to show panel
        drawField(!!activeCow);
    });

    canvas.addEventListener('mouseleave', () => {
        activeCow = null;
        drawField(false);
    });
}

// Update cow positions from MQTT data
function updateCowPositions(mqttCowData) {
    // Clear existing cow dots
    cowDots.length = 0;

    // Create new cow dots based on MQTT data
    mqttCowData.forEach(cow => {
        let canvasX, canvasY;

        // Check if collar dropped status [-99,-99]
        if (cow.pos[0] === -99 && cow.pos[1] === -99) {
            canvasX = -100;
            canvasY = -100;
        } else {
            // Use different coordinate systems based on status
            if (cow.status === 0) {
                // Status 0: Inner fence, use inner circle coordinates
                [canvasX, canvasY] = getInnerFenceCoordinates(cow.pos[0], cow.pos[1]);
            } else {
                // Status 1: Outer fence, use outer circle coordinates
                [canvasX, canvasY] = getOuterFenceCoordinates(cow.pos[0], cow.pos[1]);
            }
        }

        // Color based on status: 0 = brown (safe), 1 = red (escaped)
        const color = cow.status === 0 ? '#8B4513' : '#dd2222';

        cowDots.push({
            x: canvasX,
            y: canvasY,
            r: 12,
            color: color,
            id: cow.id,
            status: cow.status,
            gridPos: cow.pos
        });
    });

    // If canvas is displayed, redraw
    const overlayCanvas = document.getElementById('overlayCanvas');
    if (overlayCanvas && overlayCanvas.style.display !== 'none') {
        drawField();
    }
}

if (typeof window !== 'undefined') {
    window.updateCowPositions = updateCowPositions;
}

// Initialize after page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('map.js loaded, ready to receive cow data updates');
});