/**
 * Multi-Modal Perception Tools for EVO
 *
 * AGI GAP ADDRESSED: Gap 3 - Multi-Modal Perception and Agency
 * These tools follow the existing EVO tool-injection pattern.
 */

import { failure, success, tool } from "./registry.ts";
import type { EvoTool } from "../types.ts";
import { runProcess } from "./process.ts";
import { randomUUID } from "node:crypto";
import { writeFile, unlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readFile } from "node:fs/promises";

export interface MultiModalConfig {
  visionBaseUrl?: string;
  visionApiKey?: string;
  visionModel?: string;
  transcriptionEndpoint?: string;
  transcriptionApiKey?: string;
}

function imageUnderstandTool(config: MultiModalConfig): EvoTool {
  const hasVision = Boolean(config.visionBaseUrl && config.visionApiKey);
  return tool(
    "image_understand",
    hasVision
      ? "Understand and describe an image using a vision-capable LLM."
      : "[LIMITED] Basic image metadata. Configure VISION_API_KEY for full AI vision.",
    { image: { type: "string", description: "Base64 data URI or local file path." }, question: { type: "string", description: "Optional question about the image." } },
    ["image"],
    async (args) => {
      const imageInput = String(args.image ?? "");
      const question = String(args.question ?? "");
      if (!imageInput) return failure("image_understand requires 'image'.");
      let base64Image = imageInput;
      if (!imageInput.startsWith("data:")) {
        try {
          const buffer = await readFile(imageInput);
          const ext = imageInput.split(".").pop()?.toLowerCase() ?? "png";
          const mimeMap: Record<string, string> = { png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", gif: "image/gif", webp: "image/webp", bmp: "image/bmp" };
          base64Image = `data:${mimeMap[ext] ?? "image/png"};base64,${buffer.toString("base64")}`;
        } catch { return failure(`Cannot read image file: ${imageInput}`); }
      }
      if (!hasVision || !config.visionBaseUrl || !config.visionApiKey) {
        const sizeBytes = Math.round((base64Image.length * 3) / 4);
        return success(["[VISION API NOT CONFIGURED]", `Image size: ~${sizeBytes.toLocaleString()} bytes`, `Format: ${base64Image.match(/^data:([^;]+)/)?.[1] ?? "unknown"}`, "Configure VISION_BASE_URL, VISION_API_KEY, VISION_MODEL for AI vision.", question ? `Q: ${question}` : ""].filter(Boolean).join("\n"));
      }
      try {
        const response = await fetch(`${config.visionBaseUrl}/chat/completions`, {
          method: "POST", headers: { "Content-Type": "application/json", "Authorization": `Bearer ${config.visionApiKey}` },
          body: JSON.stringify({ model: config.visionModel ?? "gpt-4o", messages: [{ role: "user", content: [{ type: "text", text: question || "Describe this image in detail." }, { type: "image_url", image_url: { url: base64Image } }] }], max_tokens: 2000 }),
        });
        if (!response.ok) return failure(`Vision API error ${response.status}`);
        const data = await response.json() as Record<string, unknown>;
        const choices = data.choices as Array<{ message?: { content?: string } }> | undefined;
        return success(`Image Description:\n\n${choices?.[0]?.message?.content ?? "No description."}`);
      } catch (error) { return failure(`Vision API call failed: ${error instanceof Error ? error.message : String(error)}`); }
    },
  );
}

function audioTranscribeTool(config: MultiModalConfig): EvoTool {
  const hasAPI = Boolean(config.transcriptionEndpoint && config.transcriptionApiKey);
  return tool(
    "audio_transcribe",
    hasAPI ? "Transcribe audio from a file path or base64 data URI. Supports WAV, MP3, M4A, OGG." : "[LIMITED] Basic audio metadata. Configure TRANSCRIPTION_API_KEY for full transcription.",
    { audio: { type: "string", description: "Path to audio or base64 data URI." }, language: { type: "string", description: "Optional language code." } },
    ["audio"],
    async (args) => {
      const audioInput = String(args.audio ?? "");
      const language = String(args.language ?? "");
      if (!audioInput) return failure("audio_transcribe requires 'audio'.");
      if (!hasAPI || !config.transcriptionEndpoint || !config.transcriptionApiKey) return success("[TRANSCRIPTION API NOT CONFIGURED] Configure TRANSCRIPTION_API_KEY.");
      try {
        let fileBuffer: Uint8Array; let fileName: string;
        if (audioInput.startsWith("data:")) {
          const [_header, data] = audioInput.split(",");
          if (!data) return failure("Invalid audio data URI.");
          const headerMatch = _header?.match(/data:([^;]+)/); const mime = headerMatch?.[1] ?? "audio/wav";
          const bytes = Uint8Array.from([...atob(data)].map((c) => c.charCodeAt(0))); fileBuffer = bytes;
          const extMap: Record<string, string> = { "audio/wav": "wav", "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/ogg": "ogg", "audio/webm": "webm" };
          fileName = `audio.${extMap[mime] ?? "wav"}`;
        } else { const buf = await readFile(audioInput); fileBuffer = new Uint8Array(buf); fileName = audioInput.split("/").pop() ?? "audio.wav"; }
        const tmpPath = join(tmpdir(), `evo-audio-${randomUUID()}.${fileName.split(".").pop() ?? "wav"}`);
        await writeFile(tmpPath, fileBuffer);
        try {
          const formData = new FormData(); const blob = new Blob([fileBuffer as unknown as BlobPart]);
          formData.append("file", blob, fileName); formData.append("model", "whisper-1");
          if (language) formData.append("language", language); formData.append("response_format", "text");
          const response = await fetch(`${config.transcriptionEndpoint}/audio/transcriptions`, { method: "POST", headers: { "Authorization": `Bearer ${config.transcriptionApiKey}` }, body: formData });
          if (!response.ok) return failure(`Transcription API error ${response.status}`);
          const text = await response.text();
          return success(`Transcription:\n\n${text.trim() || "(no speech detected)"}`);
        } finally { await unlink(tmpPath).catch(() => {}); }
      } catch (error) { return failure(`Transcription failed: ${error instanceof Error ? error.message : String(error)}`); }
    },
  );
}

function cameraCaptureTool(): EvoTool {
  return tool("camera_capture", "Capture an image from a system camera. macOS: imagesnap, Linux: fswebcam.", { camera_index: { type: "integer", description: "Camera index (0 = default)." }, width: { type: "integer", description: "Capture width (default: 1280)." }, height: { type: "integer", description: "Capture height (default: 720)." } }, [],
    async (args) => {
      const cameraIndex = Number(args.camera_index ?? 0); const width = Number(args.width ?? 1280); const height = Number(args.height ?? 720);
      const tmpPath = join(tmpdir(), `evo-camera-${randomUUID()}.jpg`);
      try {
        const platform = process.platform;
        const [command, ...cmdArgs] = platform === "darwin" ? ["imagesnap", "-q", "-w", String(width / 1000), tmpPath] : platform === "linux" ? ["fswebcam", "-r", `${width}x${height}`, "--no-banner", "-d", `/dev/video${cameraIndex}`, tmpPath] : [];
        if (!command) return failure(`Camera capture not supported on ${platform}.`);
        const result = await runProcess({ command, args: cmdArgs, timeoutMs: 15_000 });
        if (result.exitCode !== 0) return failure(`Camera capture failed. Is ${command} installed?`);
        const buffer = await readFile(tmpPath); const base64 = buffer.toString("base64");
        return success(`[CAMERA CAPTURE] ${width}x${height}\ndata:image/jpeg;base64,${base64.slice(0, 200)}...`, { metadata: { capturedBase64: `data:image/jpeg;base64,${base64}`, width, height } });
      } catch (error) { return failure(`Camera capture error: ${error instanceof Error ? error.message : String(error)}`); }
      finally { await unlink(tmpPath).catch(() => {}); }
    });
}

function screenCaptureTool(): EvoTool {
  return tool("screen_capture", "Capture a screenshot. macOS: screencapture, Linux: ImageMagick import.", { region: { type: "string", description: "'interactive' for selection (macOS), or omit for full screen." } }, [],
    async (args) => {
      const region = String(args.region ?? ""); const tmpPath = join(tmpdir(), `evo-screen-${randomUUID()}.png`);
      try {
        const platform = process.platform;
        const [command, ...cmdArgs] = platform === "darwin" ? ["screencapture", ...(region === "interactive" ? ["-i"] : ["-x"]), tmpPath] : platform === "linux" ? ["import", "-window", "root", tmpPath] : [];
        if (!command) return failure(`Screen capture not supported on ${platform}.`);
        const result = await runProcess({ command, args: cmdArgs, timeoutMs: 30_000 });
        if (result.exitCode !== 0) return failure(`Screen capture failed.`);
        const buffer = await readFile(tmpPath); const base64 = buffer.toString("base64");
        return success(`[SCREEN CAPTURE]\ndata:image/png;base64,${base64.slice(0, 200)}...`, { metadata: { capturedBase64: `data:image/png;base64,${base64}` } });
      } catch (error) { return failure(`Screen capture error: ${error instanceof Error ? error.message : String(error)}`); }
      finally { await unlink(tmpPath).catch(() => {}); }
    });
}

function pdfReadTool(): EvoTool {
  return tool("pdf_read", "Extract text from a PDF file using pdftotext.", { path: { type: "string", description: "Path to PDF file." }, page: { type: "integer", description: "Optional page number." }, max_chars: { type: "integer", description: "Max characters (default: 20000)." } }, ["path"],
    async (args) => {
      const filePath = String(args.path ?? ""); const specificPage = args.page ? Number(args.page) : undefined;
      const maxChars = Number(args.max_chars ?? 20000);
      if (!filePath) return failure("pdf_read requires 'path'.");
      try {
        const pageArgs = specificPage ? ["-f", String(specificPage), "-l", String(specificPage)] : [];
        const result = await runProcess({ command: "pdftotext", args: ["-layout", ...pageArgs, filePath, "-"], timeoutMs: 30_000 });
        if (result.exitCode === 0 && result.stdout.trim()) {
          const text = result.stdout.slice(0, maxChars);
          return success(`[PDF: ${filePath}]\n${text.length.toLocaleString()} chars\n\n${text}`);
        }
        const buffer = await readFile(filePath);
        return failure(`Could not extract text. Install poppler-utils. File size: ${buffer.length.toLocaleString()} bytes.`);
      } catch (error) { return failure(`PDF read error: ${error instanceof Error ? error.message : String(error)}`); }
    });
}

export function createMultiModalTools(config: MultiModalConfig = {}): EvoTool[] {
  return [imageUnderstandTool(config), audioTranscribeTool(config), cameraCaptureTool(), screenCaptureTool(), pdfReadTool()];
}
