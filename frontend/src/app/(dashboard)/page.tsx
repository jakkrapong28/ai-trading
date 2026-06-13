"use client";

import { useEffect, useRef } from "react";
import { useDashboard } from "@/context/DashboardContext";
import { ROOMS_CONFIG, CONNECTIONS } from "@/config/dashboard";
import type { RoomDef } from "@/types";

export default function OfficeOverviewPage() {
  const { canvasRef, wrapRef, scaleMultiplierRef, frameCountRef, addChatMessage } = useDashboard();
  const centersRef = useRef<Record<string, { cx: number; cy: number }>>({});

  // ════════════════════════════════════════
  // 📐 ENGINE วาดพิกเซล NEON TECH OFFICE
  // ════════════════════════════════════════
  useEffect(() => {

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const wrap = wrapRef.current;
    if (!wrap) return;

    let W = 0, H = 0;
    const SCALE = 2;

    let scaleMultiplier = 1.0;
    let sizeX = 150;
    let sizeY = 87;
    let wallHeight = 60;
    let charScale = 1.8;
    const BOTTOM_BAR_H = 58; // height reserved for Risk Gate bar at bottom

    const getRoomCenters = (canvasW: number, canvasH: number) => {
      const centers: Record<string, { cx: number; cy: number }> = {};
      const availH = canvasH - BOTTOM_BAR_H;
      const totalH = wallHeight + 4.8 * sizeY;
      const gridCenterY = Math.max(wallHeight + 10, (availH - totalH) / 2 + wallHeight);
      const gridCenterX = canvasW / 2;

      ROOMS_CONFIG.forEach((r) => {
        const cx = gridCenterX + (r.col - r.row) * sizeX;
        const cy = gridCenterY + (r.col + r.row) * sizeY;
        centers[r.id] = { cx, cy };
      });

      return centers;
    };

    let centers = getRoomCenters(W, H);
    centersRef.current = centers;

    const resize = () => {
      const r = wrap.getBoundingClientRect();
      W = r.width;
      H = r.height;
      canvas.width = Math.floor(W * SCALE);
      canvas.height = Math.floor(H * SCALE);
      canvas.style.width = W + "px";
      canvas.style.height = H + "px";
      ctx.scale(SCALE, SCALE);

      const availableH = H - BOTTOM_BAR_H;
      const wallToSizeXRatio = 60 / 150;
      const sizeYToSizeXRatio = 87 / 150;
      const maxByH = (availableH * 0.85 - 20) / (wallToSizeXRatio + 5.2 * sizeYToSizeXRatio);
      const maxByW = (W * 0.85) / 6.0;
      const targetSizeX = Math.min(maxByH, maxByW);
      scaleMultiplier = Math.max(0.25, Math.min(1.1, targetSizeX / 150));
      scaleMultiplierRef.current = scaleMultiplier;
      sizeX = Math.round(150 * scaleMultiplier);
      sizeY = Math.round(87 * scaleMultiplier);
      wallHeight = Math.round(60 * scaleMultiplier);

      centers = getRoomCenters(W, H);
      centersRef.current = centers;
    };

    resize();

    let animFrameId: number;

    const roundRect = (c: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) => {
      c.beginPath();
      c.moveTo(x + r, y);
      c.lineTo(x + w - r, y);
      c.quadraticCurveTo(x + w, y, x + w, y + r);
      c.lineTo(x + w, y + h - r);
      c.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      c.lineTo(x + r, y + h);
      c.quadraticCurveTo(x, y + h, x, y + h - r);
      c.lineTo(x, y + r);
      c.quadraticCurveTo(x, y, x + r, y);
      c.closePath();
    };

    const drawRoom = (r: RoomDef) => {
      const pos = centers[r.id];
      if (!pos) return;
      const { cx, cy } = pos;

      ctx.fillStyle = r.color;
      ctx.beginPath();
      ctx.moveTo(cx, cy - sizeY);
      ctx.lineTo(cx + sizeX, cy);
      ctx.lineTo(cx, cy + sizeY);
      ctx.lineTo(cx - sizeX, cy);
      ctx.closePath();
      ctx.fill();

      ctx.strokeStyle = r.border + "33";
      ctx.lineWidth = 0.8;
      const step = 4;
      for (let i = 1; i < step; i++) {
        const offsetPct = i / step;
        const xStart1 = cx - sizeX + sizeX * offsetPct;
        const yStart1 = cy + sizeY * offsetPct;
        ctx.beginPath();
        ctx.moveTo(xStart1, yStart1);
        ctx.lineTo(xStart1 + sizeX, yStart1 - sizeY);
        ctx.stroke();

        const xStart2 = cx + sizeX - sizeX * offsetPct;
        const yStart2 = cy + sizeY * offsetPct;
        ctx.beginPath();
        ctx.moveTo(xStart2, yStart2);
        ctx.lineTo(xStart2 - sizeX, yStart2 - sizeY);
        ctx.stroke();
      }

      ctx.strokeStyle = r.border;
      ctx.lineWidth = 1.5;
      ctx.shadowColor = r.border;
      ctx.shadowBlur = 6;
      ctx.beginPath();
      ctx.moveTo(cx, cy - sizeY);
      ctx.lineTo(cx + sizeX, cy);
      ctx.lineTo(cx, cy + sizeY);
      ctx.lineTo(cx - sizeX, cy);
      ctx.closePath();
      ctx.stroke();
      ctx.shadowBlur = 0;
    };

    const drawRoomNameplate = (r: RoomDef) => {
      const pos = centers[r.id];
      if (!pos) return;
      const { cx, cy } = pos;

      const S = scaleMultiplier;
      const titleFont = `bold ${Math.max(11, Math.round(13 * S))}px "Manrope", sans-serif`;
      const subtitleFont = `${Math.max(9, Math.round(10.5 * S))}px "Manrope", sans-serif`;

      ctx.font = titleFont;
      const titleText = `${r.emoji} ${r.name}`;
      const titleWidth = ctx.measureText(titleText).width;

      ctx.font = subtitleFont;
      const subtitleText = r.role;
      const subtitleWidth = ctx.measureText(subtitleText).width;

      const paddingX = 14 * S;
      const dotRadius = Math.max(3.5, 4.5 * S);
      const dotSpacing = 8 * S;

      const contentWidth = Math.max(titleWidth + dotSpacing + dotRadius * 2, subtitleWidth);
      const badgeW = contentWidth + paddingX * 2;
      const badgeH = Math.max(38, Math.round(44 * S));

      const badgeX = cx - badgeW / 2;
      let badgeY = cy + sizeY - badgeH / 2 + 4 * S;

      const maxBadgeBottom = H - 64;
      if (badgeY + badgeH > maxBadgeBottom) {
        badgeY = maxBadgeBottom - badgeH;
      }

      ctx.save();
      ctx.fillStyle = "rgba(7, 10, 15, 0.96)";
      ctx.strokeStyle = r.border;
      ctx.lineWidth = 1.8;
      ctx.shadowColor = r.border;
      ctx.shadowBlur = 8;
      roundRect(ctx, badgeX, badgeY, badgeW, badgeH, Math.max(4, 6 * S));
      ctx.fill();
      ctx.stroke();
      ctx.restore();

      ctx.save();
      ctx.textBaseline = "middle";
      ctx.textAlign = "left";

      const titleGroupW = titleWidth + dotSpacing + dotRadius * 2;
      const titleStartX = badgeX + (badgeW - titleGroupW) / 2;
      const firstLineY = badgeY + badgeH * 0.35;

      ctx.font = titleFont;
      ctx.fillStyle = "#ffffff";
      ctx.fillText(titleText, titleStartX, firstLineY);

      const dotX = titleStartX + titleWidth + dotSpacing + dotRadius;
      const dotY = firstLineY;
      
      const getStatusColor = (roomId: string, status: string) => {
        if (roomId === "ea") return "#818cf8"; // Purple for EA Bot
        if (roomId === "risk") return "#ef4444"; // Red for Risk AI
        if (roomId === "strategy" || roomId === "alert") return "#fbbf24"; // Orange/Yellow
        return "#10b981"; // Green for others
      };
      const dotColor = getStatusColor(r.id, r.status);

      ctx.fillStyle = dotColor;
      ctx.beginPath();
      ctx.arc(dotX, dotY, dotRadius, 0, Math.PI * 2);
      ctx.fill();

      // Pulsing status ring
      if (r.status !== "idle") {
        ctx.fillStyle = dotColor + "22";
        ctx.beginPath();
        ctx.arc(dotX, dotY, dotRadius * 2 + Math.sin(frameCountRef.current * 0.12) * 1.5 * S, 0, Math.PI * 2);
        ctx.fill();
      }

      const secondLineY = badgeY + badgeH * 0.72;
      ctx.textAlign = "center";
      ctx.font = subtitleFont;
      ctx.fillStyle = r.labelColor;
      ctx.fillText(subtitleText, cx, secondLineY);

      ctx.restore();
    };

    const drawNetworkConnections = () => {
      CONNECTIONS.forEach((conn, idx) => {
        const p1 = centers[conn.from];
        const p2 = centers[conn.to];
        if (!p1 || !p2) return;

        // Draw solid connection line
        ctx.save();
        ctx.strokeStyle = conn.color + "44"; // Translucent for cyber aesthetic
        ctx.lineWidth = 1.5;
        ctx.shadowColor = conn.color;
        ctx.shadowBlur = 4;
        ctx.beginPath();
        ctx.moveTo(p1.cx, p1.cy);
        ctx.lineTo(p2.cx, p2.cy);
        ctx.stroke();
        ctx.restore();

        // Flowing data packet animation
        const speed = 0.008;
        const offset = idx * 0.12;
        const progress = ((frameCountRef.current * speed) + offset) % 1.0;
        
        const px = p1.cx + (p2.cx - p1.cx) * progress;
        const py = p1.cy + (p2.cy - p1.cy) * progress;

        ctx.save();
        ctx.fillStyle = conn.color;
        ctx.shadowColor = conn.color;
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      });
    };

    const render = () => {
      ctx.clearRect(0, 0, W, H);

      // 1. Dark architectural gradient base
      const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
      bgGrad.addColorStop(0, "#050810");
      bgGrad.addColorStop(0.4, "#080c18");
      bgGrad.addColorStop(1, "#04060e");
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, W, H);

      // 2. Subtle isometric grid floor
      ctx.strokeStyle = "rgba(30, 58, 138, 0.08)";
      ctx.lineWidth = 0.5;
      const gridSpacingX = sizeX / 2;
      
      if (gridSpacingX > 0 && !isNaN(gridSpacingX) && sizeY > 0 && !isNaN(sizeY)) {
        // Draw diagonal lines in direction 1 (top-left to bottom-right)
        for (let offset = -W; offset < W; offset += gridSpacingX) {
          ctx.beginPath();
          ctx.moveTo(offset, 0);
          ctx.lineTo(offset + H * (sizeX / sizeY), H);
          ctx.stroke();
        }
        // Draw diagonal lines in direction 2 (top-right to bottom-left)
        for (let offset = 0; offset < W + H * (sizeX / sizeY); offset += gridSpacingX) {
          ctx.beginPath();
          ctx.moveTo(offset, 0);
          ctx.lineTo(offset - H * (sizeX / sizeY), H);
          ctx.stroke();
        }
      }

      // 3. Large ambient glow in center (halo)
      const centerGlow = ctx.createRadialGradient(W/2, H*0.45, 40, W/2, H*0.45, W*0.55);
      centerGlow.addColorStop(0, "rgba(15, 30, 80, 0.35)");
      centerGlow.addColorStop(0.5, "rgba(8, 15, 40, 0.15)");
      centerGlow.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = centerGlow;
      ctx.fillRect(0, 0, W, H);


      // Draw glowing network lines and packets
      drawNetworkConnections();

      // Draw room diamond bases
      ROOMS_CONFIG.forEach(drawRoom);

      frameCountRef.current++;

      // Draw all unified room nameplate badges
      ROOMS_CONFIG.forEach(drawRoomNameplate);

      animFrameId = requestAnimationFrame(render);
    };

    render();

    const handleResize = () => {
      resize();
      centers = getRoomCenters(W, H);
      centersRef.current = centers;
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(animFrameId);
      window.removeEventListener("resize", handleResize);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    ROOMS_CONFIG.forEach((r) => {
      const pos = centersRef.current[r.id];
      if (!pos) return;

      const dist = Math.sqrt(Math.pow(mx - pos.cx, 2) + Math.pow(my - pos.cy, 2));
      
      if (dist < 50 * scaleMultiplierRef.current) {
        addChatMessage("system", `📌 ตรวจเช็คข้อมูลเอเจนต์ประจำแผนก: ${r.name} [${r.role}] — สแตนบายพร้อมอัปเดตสถิติ`);
      }
    });
  };

  return (
    <div className="flex-1 relative overflow-hidden bg-[#000000]" ref={wrapRef}>
      <canvas
        id="office"
        ref={canvasRef}
        onClick={handleCanvasClick}
        className="block w-full h-full cursor-pointer"
      />
    </div>
  );
}
