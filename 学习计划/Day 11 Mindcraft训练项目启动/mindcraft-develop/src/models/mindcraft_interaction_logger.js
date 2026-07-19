/*
Structured local-only logging for the Mindcraft LoRA adapter.

Each line is one JSON object so later scripts can review accepted commands,
blocked requests, gateway failures, and game feedback without parsing console text.
*/

import { appendFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';


const MODELS_DIR = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_LOG_DIR = path.resolve(
    MODELS_DIR,
    '../../../../Day 19 交互轨迹自动记录与数据扩展/logs',
);


function safeFilePart(value) {
    return String(value || 'mindcraft')
        .replace(/[^a-zA-Z0-9_-]/g, '_')
        .slice(0, 48);
}


export class MindcraftInteractionLogger {
    constructor({agentName, logDir} = {}) {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const name = safeFilePart(agentName);
        this.sessionId = `${name}-${timestamp}`;
        this.logDir = logDir || DEFAULT_LOG_DIR;
        this.filePath = path.join(this.logDir, `mindcraft_interactions_${this.sessionId}.jsonl`);
        this.sequence = 0;
        this.writeQueue = mkdir(this.logDir, {recursive: true});
    }

    write(event, details = {}) {
        const record = {
            schema_version: '1.0',
            timestamp: new Date().toISOString(),
            session_id: this.sessionId,
            sequence: ++this.sequence,
            event,
            ...details,
        };
        const line = `${JSON.stringify(record)}\n`;

        // Serialize appends so concurrent game callbacks cannot interleave JSON lines.
        this.writeQueue = this.writeQueue
            .then(() => appendFile(this.filePath, line, 'utf8'))
            .catch(error => {
                console.error(`Mindcraft interaction log write failed: ${error.message}`);
            });
        return this.writeQueue;
    }
}
