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
const SCALE = 18;
const CANVAS_WIDTH = INDOOR_WIDTH * SCALE;
const CANVAS_HEIGHT = (INDOOR_HEIGHT + OUTDOOR_HEIGHT + 2) * SCALE;

// Colors
const COLORS = {
  background: 0x1a1a2e,
  indoor: 0x252540,
  outdoor: 0x1e1e32,
  wall: 0x4a4a6c,
  door: 0x22c55e,
  doorClosed: 0xef4444,
  agent: 0x3b82f6,
  agentSlow: 0x06b6d4,
  agentPanic: 0xef4444,
  agentSeated: 0x8b5cf6,     // Purple for seated
  agentQueuing: 0xf59e0b,    // Amber for queuing
  agentFindingSeat: 0x22d3ee, // Cyan for finding seat
  heatmapLow: 0x22c55e,
  heatmapMed: 0xeab308,
  heatmapHigh: 0xef4444,
};

// Agent behavioral state codes (from backend)
const AGENT_STATE = {
  QUEUING: 0,
  WALKING: 1,
  ENTERING: 2,
  FINDING_SEAT: 3,
  SEATED: 4,
  EVACUATING: 5,
  WANDERING: 6
};

export default function FloorCanvas({ simState, onCanvasClick }) {
  const containerRef = useRef(null);
  const appRef = useRef(null);
  const agentContainerRef = useRef(null);
  const heatmapContainerRef = useRef(null);
  const staticContainerRef = useRef(null);

  // Initialize PIXI
  useEffect(() => {
    if (!containerRef.current || appRef.current) return;

    const app = new PIXI.Application({
      width: CANVAS_WIDTH,
      height: CANVAS_HEIGHT,
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
    
    app.stage.addChild(heatmapContainer);
    app.stage.addChild(staticContainer);
    app.stage.addChild(agentContainer);
    
    heatmapContainerRef.current = heatmapContainer;
    agentContainerRef.current = agentContainer;
    staticContainerRef.current = staticContainer;

    // Handle click for panic injection
    app.stage.interactive = true;
    app.stage.hitArea = new PIXI.Rectangle(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
    app.stage.on('pointerdown', (event) => {
      const pos = event.data.global;
      const simX = pos.x / SCALE;
      const simY = (CANVAS_HEIGHT - pos.y) / SCALE - OUTDOOR_HEIGHT - 1;
      if (onCanvasClick) {
        onCanvasClick(simX, simY);
      }
    });

    return () => {
      app.destroy(true, { children: true, texture: true, baseTexture: true });
      appRef.current = null;
    };
  }, []);

  // Redraw static elements when scenario changes
  useEffect(() => {
    if (!appRef.current || !staticContainerRef.current) return;
    
    const staticContainer = staticContainerRef.current;
    staticContainer.removeChildren();
    
    const scenarioType = simState?.scenario_type || 'basic';
    const gateState = simState?.gate || 'OPEN';
    const zones = simState?.zones || null;
    const lanes = simState?.lanes || null;
    const stadiumStats = simState?.stadium || null;
    
    drawStaticElements(staticContainer, gateState, scenarioType, zones, lanes, stadiumStats);
  }, [simState?.scenario_type, simState?.gate, simState?.stadium?.total_seated]);

  // Update on state change
  useEffect(() => {
    if (!appRef.current || !simState) return;

    const agentContainer = agentContainerRef.current;
    const heatmapContainer = heatmapContainerRef.current;

    // Clear previous frame
    agentContainer.removeChildren();
    heatmapContainer.removeChildren();

    // Draw heatmap
    if (simState.indoor_heatmap) {
      drawHeatmap(heatmapContainer, simState.indoor_heatmap, 'indoor');
    }
    if (simState.outdoor_heatmap) {
      drawHeatmap(heatmapContainer, simState.outdoor_heatmap, 'outdoor');
    }

    // Draw agents
    drawAgents(agentContainer, simState.agents);

    // Update door color based on gate state
    updateDoorColor(appRef.current.stage, simState.gate);

  }, [simState]);

  return (
    <div 
      ref={containerRef} 
      className="rounded-lg overflow-hidden border-2 border-sim-border"
      style={{ width: CANVAS_WIDTH, height: CANVAS_HEIGHT }}
    />
  );
}

function drawStaticElements(container, gateState, scenarioType, zones, lanes, stadiumStats) {
  const graphics = new PIXI.Graphics();
  
  // Indoor area background
  graphics.beginFill(COLORS.indoor, 0.3);
  graphics.drawRect(0, 0, CANVAS_WIDTH, INDOOR_HEIGHT * SCALE);
  graphics.endFill();

  // Outdoor area background
  graphics.beginFill(COLORS.outdoor, 0.3);
  graphics.drawRect(0, INDOOR_HEIGHT * SCALE + SCALE, CANVAS_WIDTH, OUTDOOR_HEIGHT * SCALE);
  graphics.endFill();

  // Walls
  graphics.lineStyle(3, COLORS.wall);
  
  // Indoor walls
  // Left wall
  graphics.moveTo(0, 0);
  graphics.lineTo(0, INDOOR_HEIGHT * SCALE);
  
  // Right wall
  graphics.moveTo(CANVAS_WIDTH, 0);
  graphics.lineTo(CANVAS_WIDTH, INDOOR_HEIGHT * SCALE);
  
  // Top wall
  graphics.moveTo(0, 0);
  graphics.lineTo(CANVAS_WIDTH, 0);
  
  // Bottom wall with door gap
  const doorLeft = (DOOR_X - DOOR_WIDTH / 2) * SCALE;
  const doorRight = (DOOR_X + DOOR_WIDTH / 2) * SCALE;
  graphics.moveTo(0, INDOOR_HEIGHT * SCALE);
  graphics.lineTo(doorLeft, INDOOR_HEIGHT * SCALE);
  graphics.moveTo(doorRight, INDOOR_HEIGHT * SCALE);
  graphics.lineTo(CANVAS_WIDTH, INDOOR_HEIGHT * SCALE);

  // Door indicator
  const doorColor = gateState === 'OPEN' ? COLORS.door : 
                    gateState === 'THROTTLE' ? 0xeab308 : COLORS.doorClosed;
  graphics.lineStyle(4, doorColor);
  graphics.moveTo(doorLeft, INDOOR_HEIGHT * SCALE);
  graphics.lineTo(doorRight, INDOOR_HEIGHT * SCALE);

  // Draw scenario-specific elements
  drawScenarioSpecificElements(graphics, scenarioType, zones, lanes, stadiumStats);

  container.addChild(graphics);

  // Zone labels (scenario-aware)
  drawScenarioLabels(container, scenarioType);
}

function drawScenarioSpecificElements(graphics, scenarioType, zones, lanes, stadiumStats) {
  graphics.lineStyle(2, 0x6366f1, 0.6); // Indigo dividers
  
  switch (scenarioType) {
    case 'stadium':
      // Draw 3 realistic stadium stands (left, center, right)
      const stands = [
        { id: 'left', name: 'Stand A', x: 0, y: 0, w: 6, h: 12, entrance: [3, 12] },
        { id: 'center', name: 'Stand B', x: 7, y: 0, w: 6, h: 8, entrance: [10, 8] },
        { id: 'right', name: 'Stand C', x: 14, y: 0, w: 6, h: 12, entrance: [17, 12] }
      ];
      
      stands.forEach(stand => {
        const sx = stand.x * SCALE;
        const sy = (INDOOR_HEIGHT - stand.y - stand.h) * SCALE;
        const sw = stand.w * SCALE;
        const sh = stand.h * SCALE;
        
        // Get stand status
        const standStats = stadiumStats?.stands?.[stand.id];
        const isFull = standStats?.current >= standStats?.capacity;
        const utilization = standStats?.utilization || 0;
        
        // Stand background with fill based on capacity
        const fillColor = isFull ? 0xef4444 : (utilization > 80 ? 0xf59e0b : 0x22c55e);
        graphics.beginFill(fillColor, 0.15);
        graphics.lineStyle(2, fillColor, 0.8);
        graphics.drawRect(sx, sy, sw, sh);
        graphics.endFill();
        
        // Draw seat rows (horizontal lines)
        graphics.lineStyle(1, 0x6366f1, 0.3);
        const rowSpacing = 1.2 * SCALE;
        for (let row = sy + rowSpacing; row < sy + sh - 5; row += rowSpacing) {
          graphics.moveTo(sx + 5, row);
          graphics.lineTo(sx + sw - 5, row);
        }
        
        // Draw entrance gate
        const ex = stand.entrance[0] * SCALE;
        const ey = (INDOOR_HEIGHT - stand.entrance[1]) * SCALE;
        graphics.lineStyle(3, isFull ? 0xef4444 : 0x22c55e);
        graphics.moveTo(ex - 10, ey);
        graphics.lineTo(ex + 10, ey);
        
        // Stand label with capacity
        const labelText = standStats 
          ? `${stand.name} (${standStats.current}/${standStats.capacity})`
          : stand.name;
        const text = new PIXI.Text(labelText, {
          fontFamily: 'Inter, sans-serif',
          fontSize: 10,
          fill: isFull ? 0xef4444 : 0x6366f1,
          fontWeight: 'bold',
        });
        text.anchor.set(0.5);
        text.x = sx + sw / 2;
        text.y = sy + 12;
        graphics.parent?.addChild(text);
        
        // Gate status label
        if (stadiumStats) {
          const gateText = new PIXI.Text(isFull ? '🔒 FULL' : '✓ OPEN', {
            fontFamily: 'Inter, sans-serif',
            fontSize: 8,
            fill: isFull ? 0xef4444 : 0x22c55e,
          });
          gateText.anchor.set(0.5);
          gateText.x = ex;
          gateText.y = ey + 10;
          graphics.parent?.addChild(gateText);
        }
      });
      
      // Draw central walkway/concourse
      graphics.lineStyle(1, 0x8888aa, 0.4);
      graphics.beginFill(0x1a1a2e, 0.5);
      graphics.drawRect(0, (INDOOR_HEIGHT - 6) * SCALE, CANVAS_WIDTH, 6 * SCALE);
      graphics.endFill();
      
      // Walkway label
      const walkwayLabel = new PIXI.Text('CONCOURSE', {
        fontFamily: 'Inter, sans-serif',
        fontSize: 9,
        fill: 0x8888aa,
      });
      walkwayLabel.anchor.set(0.5);
      walkwayLabel.x = CANVAS_WIDTH / 2;
      walkwayLabel.y = (INDOOR_HEIGHT - 3) * SCALE;
      graphics.parent?.addChild(walkwayLabel);
      break;

    case 'multi_lane':
      // 4 vertical lanes
      for (let i = 1; i < 4; i++) {
        const x = (CANVAS_WIDTH / 4) * i;
        graphics.moveTo(x, 0);
        graphics.lineTo(x, INDOOR_HEIGHT * SCALE);
      }
      
      // Lane labels
      for (let i = 0; i < 4; i++) {
        const text = new PIXI.Text(`Lane ${i + 1}`, {
          fontFamily: 'Inter, sans-serif',
          fontSize: 9,
          fill: 0x6366f1,
          fontWeight: 'bold',
        });
        text.x = (CANVAS_WIDTH / 4) * i + CANVAS_WIDTH / 8 - 20;
        text.y = 5;
        graphics.parent?.addChild(text);
      }
      break;

    case 'tiered':
      // 3 horizontal tiers (VIP, General, Student)
      graphics.moveTo(0, INDOOR_HEIGHT * SCALE / 3);
      graphics.lineTo(CANVAS_WIDTH, INDOOR_HEIGHT * SCALE / 3);
      graphics.moveTo(0, 2 * INDOOR_HEIGHT * SCALE / 3);
      graphics.lineTo(CANVAS_WIDTH, 2 * INDOOR_HEIGHT * SCALE / 3);
      
      // Tier labels
      const tierLabels = ['VIP', 'GENERAL', 'STUDENT'];
      tierLabels.forEach((label, i) => {
        const text = new PIXI.Text(label, {
          fontFamily: 'Inter, sans-serif',
          fontSize: 10,
          fill: 0x6366f1,
          fontWeight: 'bold',
        });
        text.x = 10;
        text.y = (INDOOR_HEIGHT * SCALE / 3) * i + INDOOR_HEIGHT * SCALE / 6 - 5;
        graphics.parent?.addChild(text);
      });
      break;

    case 'bidirectional':
      // Center divider for two-way flow
      graphics.lineStyle(3, 0xf59e0b, 0.8); // Orange for bidirectional
      graphics.moveTo(CANVAS_WIDTH / 2, 0);
      graphics.lineTo(CANVAS_WIDTH / 2, INDOOR_HEIGHT * SCALE);
      
      // Direction arrows
      const arrow1 = new PIXI.Text('→', {
        fontFamily: 'Arial',
        fontSize: 24,
        fill: 0xf59e0b,
      });
      arrow1.x = CANVAS_WIDTH / 4 - 12;
      arrow1.y = INDOOR_HEIGHT * SCALE / 2 - 12;
      graphics.parent?.addChild(arrow1);
      
      const arrow2 = new PIXI.Text('←', {
        fontFamily: 'Arial',
        fontSize: 24,
        fill: 0xf59e0b,
      });
      arrow2.x = 3 * CANVAS_WIDTH / 4 - 12;
      arrow2.y = INDOOR_HEIGHT * SCALE / 2 - 12;
      graphics.parent?.addChild(arrow2);
      break;

    case 'evacuation':
      // Emergency exit markers
      graphics.lineStyle(3, 0xef4444);
      graphics.beginFill(0xef4444, 0.3);
      
      // Top exit (wider)
      graphics.drawRect(CANVAS_WIDTH / 2 - 30, 0, 60, 10);
      
      const exitText = new PIXI.Text('🚨 EMERGENCY EXIT', {
        fontFamily: 'Inter, sans-serif',
        fontSize: 11,
        fill: 0xef4444,
        fontWeight: 'bold',
      });
      exitText.x = CANVAS_WIDTH / 2 - 60;
      exitText.y = 15;
      graphics.parent?.addChild(exitText);
      break;

    case 'predictive':
      // AI control zone indicator
      const aiText = new PIXI.Text('🔮 AI PREDICTIVE CONTROL', {
        fontFamily: 'Inter, sans-serif',
        fontSize: 11,
        fill: 0x8b5cf6,
        fontWeight: 'bold',
      });
      aiText.x = CANVAS_WIDTH / 2 - 85;
      aiText.y = INDOOR_HEIGHT * SCALE - 25;
      graphics.parent?.addChild(aiText);
      break;
  }
}

function drawScenarioLabels(container, scenarioType) {
  const indoorLabel = new PIXI.Text('INDOOR ZONE (Drone A)', {
    fontFamily: 'Inter, sans-serif',
    fontSize: 12,
    fill: 0x8888aa,
    fontWeight: 'bold',
  });
  indoorLabel.x = 10;
  indoorLabel.y = scenarioType === 'basic' || scenarioType === 'evacuation' ? 10 : INDOOR_HEIGHT * SCALE - 20;
  container.addChild(indoorLabel);

  const outdoorLabel = new PIXI.Text('OUTDOOR QUEUE (Drone B)', {
    fontFamily: 'Inter, sans-serif',
    fontSize: 12,
    fill: 0x8888aa,
    fontWeight: 'bold',
  });
  outdoorLabel.x = 10;
  outdoorLabel.y = INDOOR_HEIGHT * SCALE + SCALE + 10;
  container.addChild(outdoorLabel);

  // Door label
  const doorLabel = new PIXI.Text('DOOR', {
    fontFamily: 'Inter, sans-serif',
    fontSize: 10,
    fill: 0xaaaacc,
  });
  doorLabel.x = DOOR_X * SCALE - 15;
  doorLabel.y = INDOOR_HEIGHT * SCALE + 2;
  container.addChild(doorLabel);
}

function updateDoorColor(stage, gateState) {
  // Find and update door graphics
  // This is a simplified version - in production, store reference to door graphics
}

function drawHeatmap(container, heatmapData, zone) {
  const graphics = new PIXI.Graphics();
  const gridSize = heatmapData.length;
  
  const zoneWidth = zone === 'indoor' ? INDOOR_WIDTH : OUTDOOR_WIDTH;
  const zoneHeight = zone === 'indoor' ? INDOOR_HEIGHT : OUTDOOR_HEIGHT;
  const offsetY = zone === 'indoor' ? 0 : INDOOR_HEIGHT * SCALE + SCALE;
  
  const cellWidth = (zoneWidth * SCALE) / gridSize;
  const cellHeight = (zoneHeight * SCALE) / gridSize;

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
      const alpha = intensity * 0.4;

      graphics.beginFill(color, alpha);
      graphics.drawRect(
        x * cellWidth,
        offsetY + (gridSize - 1 - y) * cellHeight,
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

function drawAgents(container, agents) {
  if (!agents) return;

  const graphics = new PIXI.Graphics();

  for (const agent of agents) {
    const [x, y, vx, vy, isSlow, isPanicking, behaviorState] = agent;
    
    // Convert sim coordinates to canvas coordinates
    // Indoor: y >= 0, Outdoor: y < 0
    const canvasX = x * SCALE;
    const canvasY = y >= 0 
      ? (INDOOR_HEIGHT - y) * SCALE  // Indoor (flipped)
      : (INDOOR_HEIGHT * SCALE + SCALE) + (-y) * SCALE;  // Outdoor
    
    // Clamp to visible area
    if (canvasY < 0 || canvasY > CANVAS_HEIGHT) continue;
    if (canvasX < 0 || canvasX > CANVAS_WIDTH) continue;

    // Choose color based on agent state
    let color = COLORS.agent;
    if (behaviorState === AGENT_STATE.SEATED) {
      color = COLORS.agentSeated;
    } else if (behaviorState === AGENT_STATE.QUEUING) {
      color = COLORS.agentQueuing;
    } else if (behaviorState === AGENT_STATE.FINDING_SEAT) {
      color = COLORS.agentFindingSeat;
    } else if (isPanicking) {
      color = COLORS.agentPanic;
    } else if (isSlow) {
      color = COLORS.agentSlow;
    }

    // Draw agent as circle
    graphics.beginFill(color);
    if (behaviorState === AGENT_STATE.SEATED) {
      graphics.drawRect(canvasX - 3, canvasY - 2, 6, 4);
    } else {
      graphics.drawCircle(canvasX, canvasY, isSlow ? 4 : 5);
    }
    graphics.endFill();

    // Draw velocity direction indicator
    if (behaviorState !== AGENT_STATE.SEATED && (vx !== 0 || vy !== 0)) {
      const speed = Math.sqrt(vx * vx + vy * vy);
      if (speed > 0.1) {
        const dirX = (vx / speed) * 6;
        const dirY = -(vy / speed) * 6; // Flip Y for canvas
        graphics.lineStyle(1.5, color, 0.6);
        graphics.moveTo(canvasX, canvasY);
        graphics.lineTo(canvasX + dirX, canvasY + dirY);
      }
    }
  }

  container.addChild(graphics);
}
