import { useEffect, useRef } from 'react';
import * as PIXI from 'pixi.js';

// Dimensions
const INDOOR_WIDTH = 20;
const INDOOR_HEIGHT = 20;
const OUTDOOR_WIDTH = 20;
const OUTDOOR_HEIGHT = 15;
const DOOR_WIDTH = 2;
const DOOR_X = INDOOR_WIDTH / 2;

// Canvas scaling
const SCALE = 22; // Increased for better detail
const CANVAS_WIDTH = INDOOR_WIDTH * SCALE;
const CANVAS_HEIGHT_INDOOR = INDOOR_HEIGHT * SCALE;
const CANVAS_HEIGHT_OUTDOOR = OUTDOOR_HEIGHT * SCALE;

// Drone camera colors with surveillance theme
const COLORS = {
  background: 0x0a0a12,
  indoor: 0x1a1a28,
  outdoor: 0x151520,
  wall: 0x3a3a50,
  door: 0x22c55e,
  doorClosed: 0xef4444,
  agent: 0x3b82f6,
  agentSlow: 0x06b6d4,
  agentPanic: 0xef4444,
  heatmapLow: 0x22c55e,
  heatmapMed: 0xeab308,
  heatmapHigh: 0xef4444,
  gridLines: 0x2a2a40,
  reticle: 0x22c55e,
};

export default function DroneCameraView({ simState, onCanvasClick, droneId }) {
  const containerRef = useRef(null);
  const appRef = useRef(null);
  const agentContainerRef = useRef(null);
  const heatmapContainerRef = useRef(null);
  const hudContainerRef = useRef(null);
  const staticContainerRef = useRef(null);

  const isDroneA = droneId === 'A';
  const zone = isDroneA ? 'indoor' : 'outdoor';
  const canvasHeight = isDroneA ? CANVAS_HEIGHT_INDOOR : CANVAS_HEIGHT_OUTDOOR;

  // Initialize PIXI
  useEffect(() => {
    if (!containerRef.current || appRef.current) return;

    const app = new PIXI.Application({
      width: CANVAS_WIDTH,
      height: canvasHeight,
      backgroundColor: COLORS.background,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
    });

    containerRef.current.appendChild(app.view);
    appRef.current = app;

    // Create layers
    const heatmapContainer = new PIXI.Container();
    const staticContainer = new PIXI.Container();
    const agentContainer = new PIXI.Container();
    const hudContainer = new PIXI.Container();
    
    app.stage.addChild(heatmapContainer);
    app.stage.addChild(staticContainer);
    app.stage.addChild(agentContainer);
    app.stage.addChild(hudContainer);
    
    heatmapContainerRef.current = heatmapContainer;
    agentContainerRef.current = agentContainer;
    hudContainerRef.current = hudContainer;
    staticContainerRef.current = staticContainer;
    
    // Draw HUD overlay
    drawDroneHUD(hudContainer, droneId, CANVAS_WIDTH, canvasHeight);

    // Handle click for panic injection
    app.stage.interactive = true;
    app.stage.hitArea = new PIXI.Rectangle(0, 0, CANVAS_WIDTH, canvasHeight);
    app.stage.on('pointerdown', (event) => {
      const pos = event.data.global;
      const simX = pos.x / SCALE;
      const simY = isDroneA 
        ? INDOOR_HEIGHT - (pos.y / SCALE)
        : -(pos.y / SCALE);
      if (onCanvasClick) {
        onCanvasClick(simX, simY);
      }
    });

    return () => {
      app.destroy(true, { children: true, texture: true, baseTexture: true });
      appRef.current = null;
    };
  }, [droneId]);

  // Redraw static elements when scenario changes
  useEffect(() => {
    if (!appRef.current || !staticContainerRef.current) return;
    
    const staticContainer = staticContainerRef.current;
    staticContainer.removeChildren();
    
    const scenarioType = simState?.scenario_type || 'basic';
    const gateState = simState?.gate || 'OPEN';
    
    drawStaticElements(staticContainer, zone, gateState, scenarioType);
  }, [simState?.scenario_type, simState?.gate, zone]);

  // Update on state change
  useEffect(() => {
    if (!appRef.current || !simState) return;

    const agentContainer = agentContainerRef.current;
    const heatmapContainer = heatmapContainerRef.current;
    const hudContainer = hudContainerRef.current;

    // Clear previous frame
    agentContainer.removeChildren();
    heatmapContainer.removeChildren();

    // Draw heatmap
    const heatmapData = isDroneA ? simState.indoor_heatmap : simState.outdoor_heatmap;
    if (heatmapData) {
      drawHeatmap(heatmapContainer, heatmapData, zone, canvasHeight);
    }

    // Draw agents (filtered by zone)
    const filteredAgents = (simState.agents || []).filter(agent => {
      const [x, y] = agent;
      return isDroneA ? y >= 0 : y < 0;
    });
    drawAgents(agentContainer, filteredAgents, zone, canvasHeight);

    // Update HUD
    updateHUD(hudContainer, droneId, simState, CANVAS_WIDTH, canvasHeight);

  }, [simState, droneId]);

  return (
    <div className="relative">
      {/* Camera Label */}
      <div className="absolute top-2 left-2 z-10 px-3 py-1 bg-black/60 text-white text-xs font-mono border border-gray-600 rounded backdrop-blur">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${isDroneA ? 'bg-blue-500' : 'bg-emerald-500'} animate-pulse`} />
          <span>DRONE {droneId} • {zone.toUpperCase()} ZONE</span>
        </div>
      </div>

      {/* Timestamp */}
      <div className="absolute top-2 right-2 z-10 px-2 py-1 bg-black/60 text-white text-xs font-mono">
        TICK: {String(simState?.tick || 0).padStart(6, '0')}
      </div>

      {/* Canvas */}
      <div 
        ref={containerRef} 
        className="rounded-lg overflow-hidden border-2 border-gray-700 shadow-2xl drone-camera-border"
        style={{ width: CANVAS_WIDTH, height: canvasHeight }}
      />

      {/* Camera Grid Overlay */}
      <div className="absolute inset-0 pointer-events-none camera-grid" />
    </div>
  );
}

function drawStaticElements(container, zone, gateState, scenarioType) {
  const graphics = new PIXI.Graphics();
  
  const height = zone === 'indoor' ? INDOOR_HEIGHT : OUTDOOR_HEIGHT;
  const canvasHeight = height * SCALE;

  // Zone background with subtle grid - different colors based on scenario
  let bgColor = zone === 'indoor' ? COLORS.indoor : COLORS.outdoor;
  
  // Different floor appearance based on scenario type
  if (scenarioType === 'stadium') {
    bgColor = 0x2d5016; // Grass-like green for stadium
  } else if (scenarioType === 'multi_lane') {
    bgColor = 0x1a2332; // Dark blue-grey for lanes
  } else if (scenarioType === 'tiered') {
    bgColor = 0x3d2817; // Brown for tiered venue
  } else if (scenarioType === 'evacuation') {
    bgColor = 0x4a1515; // Dark red tint for emergency
  } else if (scenarioType === 'bidirectional') {
    bgColor = 0x1f3a2e; // Teal-grey for corridors
  }
  
  graphics.beginFill(bgColor, 0.4);
  graphics.drawRect(0, 0, CANVAS_WIDTH, canvasHeight);
  graphics.endFill();

  // Draw grid lines (surveillance camera aesthetic)
  graphics.lineStyle(0.5, COLORS.gridLines, 0.3);
  const gridSize = 2; // 2 meter grid
  for (let i = 0; i <= INDOOR_WIDTH; i += gridSize) {
    graphics.moveTo(i * SCALE, 0);
    graphics.lineTo(i * SCALE, canvasHeight);
  }
  for (let j = 0; j <= height; j += gridSize) {
    graphics.moveTo(0, j * SCALE);
    graphics.lineTo(CANVAS_WIDTH, j * SCALE);
  }

  // Walls
  graphics.lineStyle(4, COLORS.wall, 0.8);
  
  if (zone === 'indoor') {
    // Indoor walls
    graphics.drawRect(2, 2, CANVAS_WIDTH - 4, canvasHeight - 4);
    
    // Draw stadium sections if applicable
    if (scenarioType === 'stadium') {
      graphics.lineStyle(2, 0x88ff88, 0.4);
      // Vertical dividers for sections A, B, C, D (4 sections)
      const sectionWidth = INDOOR_WIDTH / 4;
      for (let i = 1; i < 4; i++) {
        graphics.moveTo(i * sectionWidth * SCALE, 4);
        graphics.lineTo(i * sectionWidth * SCALE, canvasHeight - 4);
      }
      // Horizontal divider
      graphics.moveTo(4, canvasHeight / 2);
      graphics.lineTo(CANVAS_WIDTH - 4, canvasHeight / 2);
    }
    
    // Draw lanes if applicable
    if (scenarioType === 'multi_lane') {
      graphics.lineStyle(2, 0x4488ff, 0.4);
      // 4 vertical lanes
      const laneWidth = INDOOR_WIDTH / 4;
      for (let i = 1; i < 4; i++) {
        graphics.moveTo(i * laneWidth * SCALE, 4);
        graphics.lineTo(i * laneWidth * SCALE, canvasHeight - 4);
      }
    }
    
    // Draw tiers if applicable
    if (scenarioType === 'tiered') {
      graphics.lineStyle(2, 0xffaa44, 0.4);
      // 3 horizontal tiers (VIP top, General middle, Student bottom)
      const tierHeight = INDOOR_HEIGHT / 3;
      graphics.moveTo(4, tierHeight * SCALE);
      graphics.lineTo(CANVAS_WIDTH - 4, tierHeight * SCALE);
      graphics.moveTo(4, tierHeight * 2 * SCALE);
      graphics.lineTo(CANVAS_WIDTH - 4, tierHeight * 2 * SCALE);
    }
    
    graphics.lineStyle(4, COLORS.wall, 0.8);
    
    // Door at bottom
    const doorLeft = (DOOR_X - DOOR_WIDTH / 2) * SCALE;
    const doorRight = (DOOR_X + DOOR_WIDTH / 2) * SCALE;
    const doorColor = gateState === 'OPEN' ? COLORS.door : 
                      gateState === 'THROTTLE' ? 0xeab308 : COLORS.doorClosed;
    graphics.lineStyle(6, doorColor, 1.0);
    graphics.moveTo(doorLeft, canvasHeight - 2);
    graphics.lineTo(doorRight, canvasHeight - 2);
  } else {
    // Outdoor boundary
    graphics.drawRect(2, 2, CANVAS_WIDTH - 4, canvasHeight - 4);
    
    // Door at top
    const doorLeft = (DOOR_X - DOOR_WIDTH / 2) * SCALE;
    const doorRight = (DOOR_X + DOOR_WIDTH / 2) * SCALE;
    graphics.lineStyle(6, COLORS.door, 1.0);
    graphics.moveTo(doorLeft, 2);
    graphics.lineTo(doorRight, 2);
  }

  container.addChild(graphics);
}

function drawDroneHUD(container, droneId, width, height) {
  const graphics = new PIXI.Graphics();
  
  // Corner brackets (camera UI aesthetic)
  const bracketSize = 20;
  const margin = 10;
  graphics.lineStyle(2, 0x00ff00, 0.6);
  
  // Top-left
  graphics.moveTo(margin, margin + bracketSize);
  graphics.lineTo(margin, margin);
  graphics.lineTo(margin + bracketSize, margin);
  
  // Top-right
  graphics.moveTo(width - margin - bracketSize, margin);
  graphics.lineTo(width - margin, margin);
  graphics.lineTo(width - margin, margin + bracketSize);
  
  // Bottom-left
  graphics.moveTo(margin, height - margin - bracketSize);
  graphics.lineTo(margin, height - margin);
  graphics.lineTo(margin + bracketSize, height - margin);
  
  // Bottom-right
  graphics.moveTo(width - margin - bracketSize, height - margin);
  graphics.lineTo(width - margin, height - margin);
  graphics.lineTo(width - margin, height - margin - bracketSize);

  // Center reticle
  const centerX = width / 2;
  const centerY = height / 2;
  graphics.lineStyle(1, COLORS.reticle, 0.4);
  graphics.drawCircle(centerX, centerY, 30);
  graphics.drawCircle(centerX, centerY, 15);
  graphics.moveTo(centerX - 40, centerY);
  graphics.lineTo(centerX - 20, centerY);
  graphics.moveTo(centerX + 20, centerY);
  graphics.lineTo(centerX + 40, centerY);
  graphics.moveTo(centerX, centerY - 40);
  graphics.lineTo(centerX, centerY - 20);
  graphics.moveTo(centerX, centerY + 20);
  graphics.lineTo(centerX, centerY + 40);

  container.addChild(graphics);
}

function updateHUD(container, droneId, simState, width, height) {
  // Clear previous HUD text
  const existingTexts = container.children.filter(child => child instanceof PIXI.Text);
  existingTexts.forEach(text => container.removeChild(text));

  // Add status info
  const droneData = droneId === 'A' ? simState.drone_a : simState.drone_b;
  if (!droneData) return;

  const infoStyle = {
    fontFamily: 'monospace',
    fontSize: 11,
    fill: 0x00ff00,
    fontWeight: 'bold',
  };

  // Bottom-left info panel
  let yPos = height - 60;
  
  if (droneId === 'A') {
    const indoorText = new PIXI.Text(
      `OCCUPANCY: ${simState.indoor_count}/${simState.capacity}`,
      infoStyle
    );
    indoorText.x = 15;
    indoorText.y = yPos;
    container.addChild(indoorText);
    
    yPos += 15;
    const crushText = new PIXI.Text(
      `CRUSH RISK: ${simState.crush_risk_index?.toFixed(1) || '0.0'}`,
      { ...infoStyle, fill: simState.crush_warning ? 0xff4444 : 0x00ff00 }
    );
    crushText.x = 15;
    crushText.y = yPos;
    container.addChild(crushText);
  } else {
    const outdoorText = new PIXI.Text(
      `QUEUE SIZE: ${simState.outdoor_count || 0}`,
      infoStyle
    );
    outdoorText.x = 15;
    outdoorText.y = yPos;
    container.addChild(outdoorText);
    
    yPos += 15;
    const gateText = new PIXI.Text(
      `GATE: ${simState.gate || 'OPEN'}`,
      { ...infoStyle, fill: simState.gate === 'OPEN' ? 0x00ff00 : 
                           simState.gate === 'THROTTLE' ? 0xeab308 : 0xff4444 }
    );
    gateText.x = 15;
    gateText.y = yPos;
    container.addChild(gateText);
  }
}

function drawHeatmap(container, heatmapData, zone, canvasHeight) {
  const graphics = new PIXI.Graphics();
  const gridSize = heatmapData.length;
  
  const cellWidth = CANVAS_WIDTH / gridSize;
  const cellHeight = canvasHeight / gridSize;

  // Find max value for normalization
  let maxVal = 0;
  for (const row of heatmapData) {
    for (const val of row) {
      maxVal = Math.max(maxVal, val);
    }
  }
  if (maxVal === 0) maxVal = 1;

  for (let y = 0; y < gridSize; y++) {
    for (let x = 0; x < gridSize; x++) {
      const val = heatmapData[y][x];
      if (val < 0.1) continue;

      const intensity = Math.min(val / maxVal, 1);
      const color = getHeatmapColor(intensity);
      const alpha = intensity * 0.5;

      graphics.beginFill(color, alpha);
      graphics.drawRect(
        x * cellWidth,
        (gridSize - 1 - y) * cellHeight,
        cellWidth,
        cellHeight
      );
      graphics.endFill();
    }
  }

  container.addChild(graphics);
}

function getHeatmapColor(intensity) {
  if (intensity < 0.33) {
    return COLORS.heatmapLow;
  } else if (intensity < 0.66) {
    return COLORS.heatmapMed;
  }
  return COLORS.heatmapHigh;
}

function drawAgents(container, agents, zone, canvasHeight) {
  if (!agents) return;

  const graphics = new PIXI.Graphics();

  for (const agent of agents) {
    const [x, y, vx, vy, isSlow, isPanicking] = agent;
    
    // Convert sim coordinates to canvas coordinates
    const canvasX = x * SCALE;
    const canvasY = zone === 'indoor'
      ? (INDOOR_HEIGHT - y) * SCALE
      : (-y) * SCALE;
    
    // Clamp to visible area
    if (canvasY < 0 || canvasY > canvasHeight) continue;
    if (canvasX < 0 || canvasX > CANVAS_WIDTH) continue;

    // Choose color based on agent state
    let color = COLORS.agent;
    let glowColor = COLORS.agent;
    if (isPanicking) {
      color = COLORS.agentPanic;
      glowColor = 0xff0000;
    } else if (isSlow) {
      color = COLORS.agentSlow;
      glowColor = 0x06b6d4;
    }

    // Draw glow effect (thermal camera aesthetic)
    graphics.beginFill(glowColor, 0.2);
    graphics.drawCircle(canvasX, canvasY, 8);
    graphics.endFill();

    // Draw agent
    graphics.beginFill(color, 0.9);
    graphics.drawCircle(canvasX, canvasY, isSlow ? 4 : 5);
    graphics.endFill();

    // Draw velocity direction indicator
    if (vx !== 0 || vy !== 0) {
      const speed = Math.sqrt(vx * vx + vy * vy);
      if (speed > 0.1) {
        const dirX = (vx / speed) * 8;
        const dirY = -(vy / speed) * 8;
        graphics.lineStyle(2, color, 0.8);
        graphics.moveTo(canvasX, canvasY);
        graphics.lineTo(canvasX + dirX, canvasY + dirY);
      }
    }
  }

  container.addChild(graphics);
}
