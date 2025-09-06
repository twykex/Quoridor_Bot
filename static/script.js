// static/script.js (Web GUI V4 - Readable Format - Final Fixes)

// --- Constants & Global Vars ---
const POLLING_INTERVAL_MS = 1000; // How often to check for game state updates
const BOARD_SIZE_INPUT = document.getElementById('board-size');
const HUMAN_PLAYER_ID_INPUT = document.getElementById('human-player-id');
const BOARD_SIZE = BOARD_SIZE_INPUT ? parseInt(BOARD_SIZE_INPUT.value) : 9;
const HUMAN_PLAYER_ID = HUMAN_PLAYER_ID_INPUT ? parseInt(HUMAN_PLAYER_ID_INPUT.value) : 2; // Default to P2 if not set
const SVG_NS = "http://www.w3.org/2000/svg";

// --- DOM Elements ---
const svgBoard = document.getElementById('quoridor-board');
const goalLayer = document.getElementById('goal-layer');
const gridLayer = document.getElementById('grid-layer');
const wallLayer = document.getElementById('wall-layer');
const pawnLayer = document.getElementById('pawn-layer');
const potentialMoveLayer = document.getElementById('potential-move-layer');
const interactionLayer = document.getElementById('interaction-layer');
const turnInfo = document.getElementById('turn-info');
const playerInfo = document.getElementById('player-info');
const playerLabelsContainer = document.getElementById('player-labels-container');
const playerResourcesContainer = document.getElementById('player-resources-container');
const statusMessageSpan = document.getElementById('status-message');
const errorMessageSpan = document.getElementById('error-message');
const startButton = document.getElementById('start-button');
const moveInputArea = document.getElementById('move-input-area');
const selectedMoveLabel = document.getElementById('selected-move-label'); // Get label too
const selectedMoveValue = document.getElementById('selected-move-value'); // Renamed from selectedMoveSpan
const confirmMoveButton = document.getElementById('confirm-move-button');
const cancelMoveButton = document.getElementById('cancel-move-button');
const howToPlayToggle = document.querySelector('.how-to-play h2');
const howToPlayContent = document.querySelector('.how-to-play .rules-content');

// --- SVG/Drawing Configuration ---
let CELL_SIZE = 55;
let WALL_THICKNESS = 10;
let PAWN_RADIUS_FACTOR = 3.3;
let CANVAS_PADDING = CELL_SIZE / 2;
const WALL_CLICK_THRESHOLD = () => CELL_SIZE * 0.15; // How close to a grid line counts as wall click

// --- Game State ---
let isGameOver = false;
let gameActive = false;
let pollingIntervalId = null;
let currentGameState = {}; // Store the latest game state
let pendingMove = null; // { type: 'MOVE'/'WALL', value: 'E4' or 'WALL H D5' }
let validHumanMoves = { pawn: [], wall: [] }; // Store valid move coords/strings for highlighting

// --- Coordinate Conversion & Helpers ---
function calculateSizes() {
    // Use clientWidth - reliable after layout
    const svgWidth = svgBoard.clientWidth;
    if (svgWidth <= 0) {
        console.warn("SVG width is 0, skipping size calculation.");
        return false; // Indicate calculation failed
    }
    CELL_SIZE = svgWidth / (BOARD_SIZE + 1); // +1 for padding concept
    WALL_THICKNESS = Math.max(4, CELL_SIZE / 5.5);
    PAWN_RADIUS_FACTOR = 3.3;
    CANVAS_PADDING = CELL_SIZE / 2;
    const viewboxSize = svgWidth;
    // Only update viewBox if it actually changed to avoid unnecessary reflows
    if (svgBoard.getAttribute('viewBox') !== `0 0 ${viewboxSize} ${viewboxSize}`) {
        svgBoard.setAttribute('viewBox', `0 0 ${viewboxSize} ${viewboxSize}`);
    }
    // Update root CSS variables if needed for other styling based on CELL_SIZE
    // document.documentElement.style.setProperty('--cell-size', `${CELL_SIZE}px`);
    return true; // Indicate success
}

function gamePosToSvgCoords(r, c) {
    // Converts game grid (row, col) 0-indexed to SVG pixel center (x, y).
    const x = CANVAS_PADDING + c * CELL_SIZE + CELL_SIZE / 2;
    const y = CANVAS_PADDING + r * CELL_SIZE + CELL_SIZE / 2;
    return { x, y };
}

function getWallSvgCoords(orientation, r, c) {
    // Calculates SVG line coordinates { x1, y1, x2, y2 } for a visual wall
    const base_x = CANVAS_PADDING + c * CELL_SIZE;
    const base_y = CANVAS_PADDING + r * CELL_SIZE;
    const center_x = base_x + CELL_SIZE; // Intersection point X
    const center_y = base_y + CELL_SIZE; // Intersection point Y
    const offset = WALL_THICKNESS / 2.5; // Adjust for rounded caps

    if (orientation === 'H') {
        const y = center_y;
        const x1 = base_x + offset;
        const x2 = base_x + 2 * CELL_SIZE - offset;
        return { x1, y1: y, x2, y2: y };
    } else if (orientation === 'V') {
        const x = center_x;
        const y1 = base_y + offset;
        const y2 = base_y + 2 * CELL_SIZE - offset;
        return { x1: x, y1, x2: x, y2 };
    }
    return null;
}

function getInteractionWallCoords(orientation, r, c) {
    // Get coordinates for the *clickable* area for wall placement (grid intersection)
    const base_x = CANVAS_PADDING + c * CELL_SIZE;
    const base_y = CANVAS_PADDING + r * CELL_SIZE;
    const center_x = base_x + CELL_SIZE;
    const center_y = base_y + CELL_SIZE;
    // Make clickable area slightly larger than visual thickness
    const clickSize = Math.min(CELL_SIZE / 2.5, WALL_THICKNESS * 1.8);

    if (orientation === 'H') {
        // Centered vertically on the line, spans horizontally
        return { x: center_x - clickSize, y: center_y - clickSize / 2, width: clickSize * 2, height: clickSize };
    } else if (orientation === 'V') {
        // Centered horizontally on the line, spans vertically
        return { x: center_x - clickSize / 2, y: center_y - clickSize, width: clickSize, height: clickSize * 2 };
    }
    return null;
}

function createSvgElement(tag) {
    return document.createElementNS(SVG_NS, tag);
}

function posToCoord(r, c) {
    // Converts 0-indexed (row, col) to 'A1' style string
    if (r < 0 || r >= BOARD_SIZE || c < 0 || c >= BOARD_SIZE) return null;
    return String.fromCharCode('A'.charCodeAt(0) + c) + (r + 1);
}

function coordToPos(coord) {
    // Converts 'A1' style string to 0-indexed {r, c} object
    if (!coord || coord.length < 2) return null;
    const colChar = coord.charAt(0).toUpperCase();
    const rowStr = coord.substring(1);
    const c = colChar.charCodeAt(0) - 'A'.charCodeAt(0);
    const r = parseInt(rowStr) - 1;
    if (isNaN(r) || c < 0 || c >= BOARD_SIZE || r < 0 || r >= BOARD_SIZE) return null;
    return { r, c };
}

// --- Drawing Functions ---
const PLAYER_COLORS = {
    1: { main: 'var(--p1-color)', highlight: 'var(--p1-highlight)' },
    2: { main: 'var(--p2-color)', highlight: 'var(--p2-highlight)' },
    3: { main: 'var(--p3-color)', highlight: 'var(--p3-highlight)' },
    4: { main: 'var(--p4-color)', highlight: 'var(--p4-highlight)' }
};

function addSvgDefs() {
    const defs = createSvgElement('defs');
    for (let i = 1; i <= 4; i++) {
        const grad = createSvgElement('radialGradient');
        grad.id = `p${i}Gradient`;
        grad.setAttribute('cx', '40%'); grad.setAttribute('cy', '40%'); grad.setAttribute('r', '60%');
        grad.innerHTML = `
            <stop offset="0%" style="stop-color:${PLAYER_COLORS[i].highlight}; stop-opacity:1" />
            <stop offset="100%" style="stop-color:${PLAYER_COLORS[i].main}; stop-opacity:1" />
        `;
        defs.appendChild(grad);
    }
    if (svgBoard.firstChild) {
        svgBoard.insertBefore(defs, svgBoard.firstChild);
    } else {
        svgBoard.appendChild(defs);
    }
}

function drawGridAndGoals() {
    goalLayer.innerHTML = '';
    gridLayer.innerHTML = '';

    const goalData = {
        1: { r: BOARD_SIZE - 1 }, // P1 goal is bottom row
        2: { r: 0 },              // P2 goal is top row
        3: { c: BOARD_SIZE - 1 }, // P3 goal is right column
        4: { c: 0 }               // P4 goal is left column
    };

    for (let i = 0; i < BOARD_SIZE; i++) {
        Object.keys(goalData).forEach(playerId => {
            const pId = parseInt(playerId);
            const goal = goalData[pId];
            const r = goal.r !== undefined ? goal.r : i;
            const c = goal.c !== undefined ? goal.c : i;

            const { x, y } = gamePosToSvgCoords(r, c);
            const rect = createSvgElement("rect");
            rect.setAttribute('x', String(x - CELL_SIZE / 2));
            rect.setAttribute('y', String(y - CELL_SIZE / 2));
            rect.setAttribute('width', String(CELL_SIZE));
            rect.setAttribute('height', String(CELL_SIZE));
            rect.setAttribute('class', `goal-cell goal-p${pId}`);
            goalLayer.appendChild(rect);
        });
    }

    const boardPixelSize = BOARD_SIZE * CELL_SIZE;
    for (let i = 0; i <= BOARD_SIZE; i++) {
        const coord = CANVAS_PADDING + i * CELL_SIZE;
        const v_line = createSvgElement("line");
        v_line.setAttribute('x1', String(coord));
        v_line.setAttribute('y1', String(CANVAS_PADDING));
        v_line.setAttribute('x2', String(coord));
        v_line.setAttribute('y2', String(CANVAS_PADDING + boardPixelSize));
        v_line.setAttribute('class', 'grid-line');
        gridLayer.appendChild(v_line);

        const h_line = createSvgElement("line");
        h_line.setAttribute('x1', String(CANVAS_PADDING));
        h_line.setAttribute('y1', String(coord));
        h_line.setAttribute('x2', String(CANVAS_PADDING + boardPixelSize));
        h_line.setAttribute('y2', String(coord));
        h_line.setAttribute('class', 'grid-line');
        gridLayer.appendChild(h_line);
    }
}

function drawPawns(pawnPositions, active_player) {
    pawnLayer.innerHTML = '';
    const PAWN_RADIUS = CELL_SIZE / PAWN_RADIUS_FACTOR;
    if (!pawnPositions) return;

    for (const playerIdStr in pawnPositions) {
        const playerId = parseInt(playerIdStr);
        const posStr = pawnPositions[playerId];
        if (!posStr || posStr === '?') continue;

        const pos = coordToPos(posStr);
        if (!pos) continue;

        const { x, y } = gamePosToSvgCoords(pos.r, pos.c);
        const circle = createSvgElement("circle");
        circle.setAttribute('cx', String(x));
        circle.setAttribute('cy', String(y));
        circle.setAttribute('r', String(PAWN_RADIUS));
        circle.setAttribute('class', `pawn pawn-p${playerId}`);
        if (playerId === active_player && gameActive && !isGameOver) {
            circle.classList.add('pawn-active');
        }
        pawnLayer.appendChild(circle);
    }
}

function drawWalls(walls_list) {
    // Draws the wall lines
    wallLayer.innerHTML = ''; // Clear old walls
    if (!walls_list || !Array.isArray(walls_list)) return;

    walls_list.forEach(wall_str => {
        // Expected format: "WALL H E5"
        const parts = wall_str.split(' ');
        if (parts.length !== 3 || parts[0] !== 'WALL') return;

        const orientation = parts[1]; // 'H' or 'V'
        const coord_str = parts[2];   // 'E5'

        // Convert 'E5' to {r, c} for top-left
        const pos = coordToPos(coord_str);
        // Validate wall coordinate range (A1-H8 -> 0,0 to 7,7)
        if (!pos || pos.r >= BOARD_SIZE - 1 || pos.c >= BOARD_SIZE - 1) {
             console.error(`Invalid wall coordinate received: ${coord_str}`);
             return; // Don't draw invalid walls
        }

        const coords = getWallSvgCoords(orientation, pos.r, pos.c);
        if (coords) {
            const line = createSvgElement("line");
            line.setAttribute('x1', String(coords.x1));
            line.setAttribute('y1', String(coords.y1));
            line.setAttribute('x2', String(coords.x2));
            line.setAttribute('y2', String(coords.y2));
            line.setAttribute('stroke-width', String(WALL_THICKNESS));
            line.setAttribute('class', 'wall');
            wallLayer.appendChild(line);
        }
    });
}

function drawPotentialMoves(validPawnCoords, validWallStrings) {
    // Draws highlights for valid moves
    potentialMoveLayer.innerHTML = ''; // Clear previous highlights
    const PAWN_MOVE_RADIUS = CELL_SIZE / 3.5; // Highlight radius

    // Highlight valid pawn moves (coordinates like 'E5')
    validPawnCoords.forEach(coord => {
        const pos = coordToPos(coord);
        if (!pos) return;
        const { x, y } = gamePosToSvgCoords(pos.r, pos.c);
        const circle = createSvgElement('circle');
        circle.setAttribute('cx', String(x));
        circle.setAttribute('cy', String(y));
        circle.setAttribute('r', String(PAWN_MOVE_RADIUS));
        circle.setAttribute('class', 'valid-move-highlight');
        potentialMoveLayer.appendChild(circle);
    });

    // Highlight valid wall placements (strings like 'WALL H E5')
    validWallStrings.forEach(wallStr => {
        const parts = wallStr.split(' ');
        if (parts.length !== 3) return;
        const orientation = parts[1];
        const coord = parts[2];
        const pos = coordToPos(coord); // Top-left corner pos {r, c}
        if (!pos) return;

        // Use interaction coordinates for the highlight rectangle
        const interactionCoords = getInteractionWallCoords(orientation, pos.r, pos.c);
        if (interactionCoords) {
            const rect = createSvgElement('rect');
            rect.setAttribute('x', String(interactionCoords.x));
            rect.setAttribute('y', String(interactionCoords.y));
            rect.setAttribute('width', String(interactionCoords.width));
            rect.setAttribute('height', String(interactionCoords.height));
            rect.setAttribute('rx', '3'); // Slightly rounded corners for highlight
            rect.setAttribute('class', 'valid-move-highlight');
            // Add data attribute linking highlight to interaction element ID
            rect.setAttribute('data-wall-id', `wall-${orientation}-${pos.r}-${pos.c}`);
            potentialMoveLayer.appendChild(rect);
        }
    });
}

function drawSelectionOutline(move) {
    // Draws the gold outline for the selected move
    const existing = potentialMoveLayer.querySelector('.selected-outline');
    if (existing) existing.remove(); // Clear previous selection
    if (!move) return; // Do nothing if move is null

    const PAWN_SELECT_RADIUS = CELL_SIZE / 2.5; // Selection radius

    if (move.type === 'MOVE') {
        const pos = coordToPos(move.value);
        if (!pos) return;
        const { x, y } = gamePosToSvgCoords(pos.r, pos.c);
        const circle = createSvgElement('circle');
        circle.setAttribute('cx', String(x));
        circle.setAttribute('cy', String(y));
        circle.setAttribute('r', String(PAWN_SELECT_RADIUS));
        circle.setAttribute('class', 'selected-outline');
        potentialMoveLayer.appendChild(circle);
    } else if (move.type === 'WALL') {
        const parts = move.value.split(' '); // "WALL H E5"
        if (parts.length !== 3) return;
        const orientation = parts[1];
        const coord = parts[2];
        const pos = coordToPos(coord);
        if (!pos) return;
        const coords = getWallSvgCoords(orientation, pos.r, pos.c); // Get visual wall coords
        if (coords) {
            const line = createSvgElement("line");
            line.setAttribute('x1', String(coords.x1));
            line.setAttribute('y1', String(coords.y1));
            line.setAttribute('x2', String(coords.x2));
            line.setAttribute('y2', String(coords.y2));
            // Make outline thicker than wall
            line.setAttribute('stroke-width', String(WALL_THICKNESS + 3));
            line.setAttribute('class', 'selected-outline');
            line.setAttribute('stroke-opacity', '0.8'); // Slightly transparent
            potentialMoveLayer.appendChild(line);
        }
    }
}

// --- Interaction Layer (Keep empty, click handled by svgBoard) ---
function createInteractionLayer() {
    interactionLayer.innerHTML = '';
}

// +++ NEW: Function to flash board border +++
function flashBoardError() {
    svgBoard.classList.add('board-error-flash');
    setTimeout(() => {
        svgBoard.classList.remove('board-error-flash');
    }, 600); // Duration of flash
}

// --- Game Update & Turn Logic ---
function updateInfoBar(gameState) {
    errorMessageSpan.textContent = '';
    turnInfo.textContent = `Turn: ${gameState.turn_count || '?'}`;

    const cp = gameState.current_player;
    const playerTurnLabel = cp !== undefined ? `P${cp}${cp === HUMAN_PLAYER_ID ? ' (You)' : ' (Bot)'}` : '-';
    playerInfo.textContent = `Turn: ${playerTurnLabel}`;

    if (gameState.num_players) {
        playerLabelsContainer.innerHTML = '';
        playerResourcesContainer.innerHTML = '';
        for (let i = 1; i <= gameState.num_players; i++) {
            const isHuman = i === HUMAN_PLAYER_ID;
            const icon = isHuman ? 'person' : 'smart_toy';
            const labelSpan = document.createElement('span');
            labelSpan.className = `player-label p${i}-label`;
            labelSpan.innerHTML = `<i class="material-icons">${icon}</i> P${i}: ${isHuman ? 'You' : 'Bot'}`;
            playerLabelsContainer.appendChild(labelSpan);
            if (i < gameState.num_players) {
                const vsSpan = document.createElement('span');
                vsSpan.textContent = 'vs';
                playerLabelsContainer.appendChild(vsSpan);
            }

            const resourceDiv = document.createElement('div');
            resourceDiv.className = 'player-resource';
            resourceDiv.innerHTML = `
                <span><i class="material-icons">${icon}</i> P${i} Walls:</span>
                <span id="p${i}-walls-info">${gameState.walls_left[i] !== undefined ? gameState.walls_left[i] : '?'}</span>
            `;
            playerResourcesContainer.appendChild(resourceDiv);
        }
    }

    const maxLen = 70;
    let statusMsg = gameState.status_message || (gameActive ? "Waiting..." : "Click Start Game");
    if (statusMessageSpan) {
        statusMessageSpan.textContent = statusMsg.length > maxLen ? statusMsg.substring(0, maxLen - 3) + "..." : statusMsg;
    }
}

function disableInteraction() {
    // Disables human input elements
    svgBoard.style.cursor = 'default';
    potentialMoveLayer.innerHTML = '';
    moveInputArea.classList.add('inactive');
    confirmMoveButton.disabled = true;
    pendingMove = null;
    drawSelectionOutline(null); // Clear selection outline
}

function enableHumanTurn(gameState) {
    if (!gameActive || isGameOver) return;
    errorMessageSpan.textContent = '';
    statusMessageSpan.textContent = "Your Turn! Select a move.";
    svgBoard.style.cursor = 'pointer';

    validHumanMoves.pawn = [];
    validHumanMoves.wall = [];

    const humanPosStr = gameState.pawn_positions[HUMAN_PLAYER_ID];
    const humanPos = coordToPos(humanPosStr);
    const otherPawnPositions = Object.values(gameState.pawn_positions).filter(p => p !== humanPosStr).map(coordToPos);

    if (humanPos) {
        const directions = [[0, 1], [0, -1], [1, 0], [-1, 0]];
        directions.forEach(([dr, dc]) => {
            const tr = humanPos.r + dr;
            const tc = humanPos.c + dc;
            const targetCoord = posToCoord(tr, tc);
            if (targetCoord && !otherPawnPositions.some(p => p.r === tr && p.c === tc)) {
                validHumanMoves.pawn.push(targetCoord);
            }
        });
    }
    drawPotentialMoves(validHumanMoves.pawn, validHumanMoves.wall);
    console.log("Human turn enabled. Basic pawn hints:", validHumanMoves.pawn);
}

function handleBoardClick(event) {
    // Handles clicks on the interaction layer (now svgBoard)
    if (!gameActive || isGameOver || currentGameState.current_player !== HUMAN_PLAYER_ID) {
        return; // Ignore clicks if not human's turn
    }

    // --- Get SVG Coordinates from Click ---
    const svgPoint = svgBoard.createSVGPoint();
    svgPoint.x = event.clientX;
    svgPoint.y = event.clientY;
    let pointTransformed;
    try {
        // Get the transformation matrix from screen coords to SVG coords
        const CTM = svgBoard.getScreenCTM();
        if (!CTM) throw new Error("SVG CTM is null");
        pointTransformed = svgPoint.matrixTransform(CTM.inverse());
    } catch (e) {
        console.error("Error transforming click point:", e);
        return; // Cannot proceed without correct coordinates
    }
    const clickX = pointTransformed.x;
    const clickY = pointTransformed.y;

    // --- Determine Click Type (Cell or Wall Intersection) ---
    const clickedColRaw = (clickX - CANVAS_PADDING) / CELL_SIZE;
    const clickedRowRaw = (clickY - CANVAS_PADDING) / CELL_SIZE;
    const clickedCol = Math.floor(clickedColRaw);
    const clickedRow = Math.floor(clickedRowRaw);

    const distToHorizLine = Math.abs(clickY - (CANVAS_PADDING + Math.round(clickedRowRaw) * CELL_SIZE));
    const distToVertLine = Math.abs(clickX - (CANVAS_PADDING + Math.round(clickedColRaw) * CELL_SIZE));
    const threshold = WALL_CLICK_THRESHOLD();

    let selectedAction = null;

    // --- Check for Wall Click FIRST ---
    if (distToHorizLine < threshold && clickedCol < BOARD_SIZE - 1 && clickedRowRaw > 0.1 && clickedRowRaw < BOARD_SIZE - 0.1) {
        const wallRow = Math.round(clickedRowRaw) - 1;
        const wallCol = clickedCol;
        if (wallRow >= 0 && wallRow < BOARD_SIZE - 1 && wallCol >= 0 && wallCol < BOARD_SIZE - 1) {
            const coord = posToCoord(wallRow, wallCol);
            if (coord) { selectedAction = { type: 'WALL', value: `WALL H ${coord}` }; console.log(`Potential WALL H near ${coord}`); }
        }
    }
    if (!selectedAction && distToVertLine < threshold && clickedRow < BOARD_SIZE - 1 && clickedColRaw > 0.1 && clickedColRaw < BOARD_SIZE - 0.1) {
        const wallRow = clickedRow;
        const wallCol = Math.round(clickedColRaw) - 1;
         if (wallRow >= 0 && wallRow < BOARD_SIZE - 1 && wallCol >= 0 && wallCol < BOARD_SIZE - 1) {
            const coord = posToCoord(wallRow, wallCol);
             if (coord) { selectedAction = { type: 'WALL', value: `WALL V ${coord}` }; console.log(`Potential WALL V near ${coord}`); }
        }
    }

    // --- Check for Pawn Move Click ---
    if (!selectedAction) {
        if (clickedRow >= 0 && clickedRow < BOARD_SIZE && clickedCol >= 0 && clickedCol < BOARD_SIZE) {
            const coord = posToCoord(clickedRow, clickedCol);
            selectedAction = { type: 'MOVE', value: coord };
            console.log(`Potential MOVE at ${coord}`);
        } else { console.log("Click outside board cells."); }
    }

    // --- Select the Action ---
    if (selectedAction) {
        selectMove(selectedAction);
    } else {
        console.log("Invalid click area.");
        cancelMove();
    }
}


function selectMove(moveData) {
    // Stores the selected move temporarily and updates UI
    errorMessageSpan.textContent = ''; // Clear error on new selection
    pendingMove = moveData;
    selectedMoveValue.textContent = `${moveData.type === 'MOVE' ? 'MOVE ' + moveData.value : moveData.value}`;
    drawSelectionOutline(moveData); // Show gold highlight
    moveInputArea.classList.remove('inactive'); // Show confirm/cancel UI
    confirmMoveButton.disabled = false;
}

function cancelMove() {
    // Clears the pending move selection
    errorMessageSpan.textContent = ''; // Clear error on cancel
    pendingMove = null;
    selectedMoveValue.textContent = `-`; // Reset label
    drawSelectionOutline(null);
    moveInputArea.classList.add('inactive');
    confirmMoveButton.disabled = true;
}

async function confirmMove() {
    if (!pendingMove || !gameActive || isGameOver || currentGameState.current_player !== HUMAN_PLAYER_ID) return;
    const moveToSend = pendingMove.type === 'MOVE' ? `MOVE ${pendingMove.value}` : pendingMove.value;
    console.log(`Confirming: ${moveToSend}`);
    disableInteraction(); statusMessageSpan.textContent = `Sending: ${moveToSend}...`; confirmMoveButton.disabled = true; errorMessageSpan.textContent = '';
    try {
        const response = await fetch('/make_human_move', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ move: moveToSend }) });
        if (!response.ok) throw new Error(`HTTP error! ${response.status}`);
        const data = await response.json();
        currentGameState = data.game_state || {}; gameActive = currentGameState.game_active; isGameOver = currentGameState.is_game_over;
        updateInfoBar(currentGameState); drawPawns(currentGameState.pawn_positions, currentGameState.current_player); drawWalls(currentGameState.placed_walls);
        if (!data.success) {
            const failReason = data.reason || 'Unknown Error'; console.error("Move failed:", failReason);
            errorMessageSpan.textContent = `Invalid Move: ${failReason}`; flashBoardError();
            if (!isGameOver && gameActive) enableHumanTurn(currentGameState);
        } else {
             errorMessageSpan.textContent = '';
             if (currentGameState.current_player === HUMAN_PLAYER_ID && gameActive && !isGameOver) { enableHumanTurn(currentGameState); }
             else if (gameActive && !isGameOver) { disableInteraction(); }
        }
    } catch (error) {
        console.error("Error sending move:", error); statusMessageSpan.textContent = "Error!"; errorMessageSpan.textContent = "Network/Server Error"; flashBoardError();
        if (gameActive && !isGameOver && currentGameState?.current_player === HUMAN_PLAYER_ID) {
             enableHumanTurn(currentGameState);
        } else {
             disableInteraction();
        }
    } finally {
        cancelMove();
    }
}

async function fetchAndUpdateGamePoll() {
    if (isGameOver || !gameActive) { stopPolling(); return; }
    try {
        const response = await fetch('/game_state');
        if (!response.ok) throw new Error(`HTTP error! ${response.status}`);
        const gs = await response.json();
        currentGameState = gs;
        gameActive = gs.game_active;
        isGameOver = gs.is_game_over;
        updateInfoBar(gs);
        drawPawns(gs.pawn_positions, gs.current_player);
        drawWalls(gs.placed_walls);
        if (isGameOver) {
            statusMessageSpan.textContent = `G Over! P${gs.winner} Wins!`;
            stopPolling();
            startButton.disabled = false;
            startButton.textContent = "Play Again?";
        } else if (!gameActive) {
            statusMessageSpan.textContent = "Click Start";
            stopPolling();
            startButton.disabled = false;
            startButton.textContent = "Start Game";
        } else if (gs.current_player === HUMAN_PLAYER_ID && svgBoard.style.cursor !== 'pointer') {
            enableHumanTurn(gs);
        } else if (gs.current_player !== HUMAN_PLAYER_ID) {
            disableInteraction();
        }
    } catch (error) {
        console.error("Polling error:", error);
    }
}
function startPolling() { if (pollingIntervalId) clearInterval(pollingIntervalId); pollingIntervalId = setInterval(fetchAndUpdateGamePoll, POLLING_INTERVAL_MS); console.log("Polling started."); }
function stopPolling() { if (pollingIntervalId) clearInterval(pollingIntervalId); pollingIntervalId = null; console.log("Polling stopped."); }

// --- Event Listeners Setup ---
startButton.addEventListener('click', handleStartGame);
svgBoard.addEventListener('click', handleBoardClick); // Listener on the main SVG
confirmMoveButton.addEventListener('click', confirmMove);
cancelMoveButton.addEventListener('click', cancelMove);
howToPlayToggle.addEventListener('click', () => {
    if (howToPlayContent.style.display === 'block') {
        howToPlayContent.style.display = 'none';
    } else {
        howToPlayContent.style.display = 'block';
    }
});

// Corrected Resize Listener
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        requestAnimationFrame(() => {
            console.log("Resizing...");
            if (calculateSizes()) {
                drawGridAndGoals(); drawPawns(currentGameState?.p1_pos, currentGameState?.p2_pos, currentGameState?.current_player); drawWalls(currentGameState?.placed_walls);
                // Use && corrected logic
                if (gameActive && !isGameOver && currentGameState?.current_player === HUMAN_PLAYER_ID) {
                     enableHumanTurn(currentGameState);
                 } else {
                     potentialMoveLayer.innerHTML = '';
                 }
             }
         });
     }, 150);
 });

// --- Initialization Function ---
function initialize() {
    console.log("Initializing GUI...");
    requestAnimationFrame(() => {
        if (calculateSizes()) {
            addSvgDefs(); drawGridAndGoals(); disableInteraction();
            fetch('/game_state').then(r => r.ok ? r.json() : Promise.reject(r)).then(is => {
                currentGameState = is;
                updateInfoBar(is);
                errorMessageSpan.textContent = '';
                drawPawns(is.pawn_positions, is.current_player);
                drawWalls(is.placed_walls);
                console.log("Initial state OK.");
            }).catch(e => {
                console.error("Init fetch fail", e);
                statusMessageSpan.textContent = "Error loading.";
            });
        } else {
            statusMessageSpan.textContent = "Error sizing.";
            console.error("Init size fail.");
        }
    });
    console.log("Init done. Waiting for Start Button.");
}

document.addEventListener('DOMContentLoaded', initialize);

async function handleStartGame() {
    console.log("Start clicked");
    startButton.disabled = true;
    startButton.textContent = "Starting...";
    statusMessageSpan.textContent = "Initializing...";
    errorMessageSpan.textContent = '';
    isGameOver = false;
    gameActive = false;
    stopPolling();
    try {
        const response = await fetch('/start_game', { method: 'POST' });
        if (!response.ok) throw new Error(`HTTP error! ${response.status}`);
        const data = await response.json();
        if (data.success) {
            console.log("Game started.");
            gameActive = true;
            startButton.textContent = "Game Running...";
            currentGameState = data.game_state || {};
            updateInfoBar(currentGameState);
            drawPawns(currentGameState.pawn_positions, currentGameState.current_player);
            drawWalls(currentGameState.placed_walls);
            isGameOver = currentGameState.is_game_over;
            if (currentGameState.current_player === HUMAN_PLAYER_ID && gameActive && !isGameOver) {
                enableHumanTurn(currentGameState);
            } else if (gameActive && !isGameOver) {
                statusMessageSpan.textContent = currentGameState.status_message || "Bot Thinking...";
                disableInteraction();
            }
            startPolling();
        } else {
            throw new Error(data.message || "Fail start.");
        }
    } catch (error) {
        console.error("Start error:", error);
        statusMessageSpan.textContent = "Start Error!";
        errorMessageSpan.textContent = "Failed to start.";
        startButton.disabled = false;
        startButton.textContent = "Start Game";
        gameActive = false;
        stopPolling();
    }
}

// Optional: Add simple flash function for feedback on invalid clicks
function flashElement(el, c = 'rgba(255,0,0,0.4)') { if (!el) return; const oF = el.getAttribute('fill') || 'transparent'; el.setAttribute('fill', c); setTimeout(() => { el.setAttribute('fill', oF); }, 250); }