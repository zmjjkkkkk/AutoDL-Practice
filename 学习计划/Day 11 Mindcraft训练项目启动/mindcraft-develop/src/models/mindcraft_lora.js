/*
Adapter for the loopback-only Day 17 LoRA command gateway.

The gateway, not this client, owns command validation. This adapter returns only
the gateway's approved value so Mindcraft never receives raw model output.
*/

import { MindcraftInteractionLogger } from './mindcraft_interaction_logger.js';
import { formatQueryFeedback } from './game_feedback_formatter.js';


const BLOCKED_REPLY = 'I could not map that request to a verified Mindcraft action.';
const NO_RESPONSE = '\t';


function pendingPlayerText(turns, playerName) {
    const latest = turns.at(-1);
    if (latest?.role !== 'user' || typeof latest.content !== 'string') return '';

    // Mindcraft stores player chat as "player_name: message"; Day 15 SFT used just "message".
    const match = latest.content.match(/^([^:\n]{1,48}):\s*(.*)$/s);
    if (!match || match[1].trim().toLowerCase() !== playerName.toLowerCase()) return '';
    return match[2].trim();
}


function latestSystemFeedback(turns) {
    const feedback = turns.at(-1);
    const command = turns.at(-2);
    if (feedback?.role !== 'system' || command?.role !== 'assistant') return null;

    const commandText = typeof command.content === 'string' ? command.content.trim() : '';
    const feedbackText = typeof feedback.content === 'string' ? feedback.content.trim() : '';
    if (!commandText || !feedbackText) return null;
    return {command: commandText, feedback: feedbackText};
}


function completedQueryReply(turns) {
    const result = turns.at(-1);
    const command = turns.at(-2);
    if (result?.role !== 'system' || command?.role !== 'assistant') return null;

    const commandName = command.content?.trim();
    if (!['!nearbyBlocks', '!inventory', '!stats'].includes(commandName)) return null;

    const content = typeof result.content === 'string' ? result.content.trim() : '';
    if (!content) {
        if (commandName === '!nearbyBlocks') return 'No nearby block information was returned.';
        if (commandName === '!inventory') return 'No inventory information was returned.';
        return 'No status information was returned.';
    }
    return formatQueryFeedback(commandName, content);
}


function simpleEmbedding(text, dimensions = 256) {
    const vector = new Array(dimensions).fill(0);
    for (const token of text.toLowerCase().split(/\s+/).filter(Boolean)) {
        let hash = 2166136261;
        for (const char of token) {
            hash ^= char.charCodeAt(0);
            hash = Math.imul(hash, 16777619);
        }
        vector[(hash >>> 0) % dimensions] += 1;
    }
    const norm = Math.hypot(...vector) || 1;
    return vector.map(value => value / norm);
}


export class MindcraftLora {
    static prefix = 'mindcraft_lora';

    constructor(model_name, url, params) {
        this.model_name = model_name || 'command-router';
        this.url = (url || 'http://127.0.0.1:18765').replace(/\/$/, '');
        this.timeoutMs = params?.timeout_ms || 120000;
        this.playerName = params?.player_name || 'robot';
        this.logger = new MindcraftInteractionLogger({
            agentName: this.model_name,
            logDir: params?.interaction_log_dir,
        });
        this.lastFeedbackSignature = '';
        console.log(`Mindcraft interaction log: ${this.logger.filePath}`);
    }

    async logLatestFeedback(turns) {
        const result = latestSystemFeedback(turns);
        if (!result) return;

        const signature = `${result.command}\n${result.feedback}`;
        if (signature === this.lastFeedbackSignature) return;
        this.lastFeedbackSignature = signature;
        await this.logger.write('game_feedback', {
            command: result.command,
            feedback: result.feedback,
        });
    }

    async sendRequest(turns, _systemMessage) {
        await this.logLatestFeedback(turns);
        const queryReply = completedQueryReply(turns);
        if (queryReply !== null) return queryReply;

        const text = pendingPlayerText(turns, this.playerName);
        // Respond only to a new final player message, except for the two verified query-result replies above.
        if (!text) return NO_RESPONSE;

        const requestStartedAt = Date.now();
        await this.logger.write('player_request', {
            player_text: text,
            gateway_url: this.url,
        });

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
        let httpStatus = null;
        try {
            console.log(`Awaiting Mindcraft LoRA gateway response for: ${text}`);
            const response = await fetch(`${this.url}/command`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text}),
                signal: controller.signal,
            });
            httpStatus = response.status;
            if (!response.ok) {
                throw new Error(`Gateway returned HTTP ${response.status}`);
            }

            const payload = await response.json();
            const guard = payload?.guard;
            if (guard?.accepted === true && (guard.kind === 'command' || guard.kind === 'text')) {
                console.log(`Gateway approved ${guard.kind}: ${guard.value}`);
                await this.logger.write('model_decision', {
                    player_text: text,
                    raw_model_output: payload?.raw_model_output || '',
                    guard,
                    returned_to_mindcraft: guard.value,
                    latency_ms: Date.now() - requestStartedAt,
                });
                return guard.value;
            }

            console.warn(`Gateway blocked output: ${guard?.candidate || '<empty>'} (${guard?.reason || 'unknown'})`);
            const returnedToMindcraft = typeof guard?.value === 'string' ? guard.value : BLOCKED_REPLY;
            await this.logger.write('model_decision', {
                player_text: text,
                raw_model_output: payload?.raw_model_output || '',
                guard: guard || null,
                returned_to_mindcraft: returnedToMindcraft,
                latency_ms: Date.now() - requestStartedAt,
            });
            return returnedToMindcraft;
        } catch (error) {
            console.error('Mindcraft LoRA gateway request failed:', error.message);
            await this.logger.write('gateway_error', {
                player_text: text,
                http_status: httpStatus,
                latency_ms: Date.now() - requestStartedAt,
                detail: error.message,
            });
            return 'The local command service is unavailable right now.';
        } finally {
            clearTimeout(timeout);
        }
    }

    async embed(text) {
        // The SFT adapter has no embedding head. This keeps Mindcraft's example selector operational.
        return simpleEmbedding(text);
    }
}
