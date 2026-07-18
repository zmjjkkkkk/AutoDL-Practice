/*
Adapter for the loopback-only Day 17 LoRA command gateway.

The gateway, not this client, owns command validation. This adapter returns only
the gateway's approved value so Mindcraft never receives raw model output.
*/

const BLOCKED_REPLY = 'I could not map that request to a verified Mindcraft action.';
const NO_RESPONSE = '\t';


function pendingPlayerText(turns) {
    const latest = turns.at(-1);
    if (latest?.role !== 'user' || typeof latest.content !== 'string') return '';

    // Mindcraft stores player chat as "player_name: message"; Day 15 SFT used just "message".
    return latest.content.replace(/^[^:\n]{1,48}:\s*/, '').trim();
}


function completedQueryReply(turns) {
    const result = turns.at(-1);
    const command = turns.at(-2);
    if (result?.role !== 'system' || command?.role !== 'assistant') return null;

    const commandName = command.content?.trim();
    if (commandName !== '!nearbyBlocks' && commandName !== '!inventory') return null;

    const content = typeof result.content === 'string' ? result.content.trim() : '';
    if (!content) return commandName === '!nearbyBlocks' ? 'No nearby block information was returned.' : 'No inventory information was returned.';
    return content;
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
    }

    async sendRequest(turns, _systemMessage) {
        const queryReply = completedQueryReply(turns);
        if (queryReply !== null) return queryReply;

        const text = pendingPlayerText(turns);
        // Respond only to a new final player message, except for the two verified query-result replies above.
        if (!text) return NO_RESPONSE;

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
        try {
            console.log(`Awaiting Mindcraft LoRA gateway response for: ${text}`);
            const response = await fetch(`${this.url}/command`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text}),
                signal: controller.signal,
            });
            if (!response.ok) {
                throw new Error(`Gateway returned HTTP ${response.status}`);
            }

            const payload = await response.json();
            const guard = payload?.guard;
            if (guard?.accepted === true && (guard.kind === 'command' || guard.kind === 'text')) {
                console.log(`Gateway approved ${guard.kind}: ${guard.value}`);
                return guard.value;
            }

            console.warn(`Gateway blocked output: ${guard?.candidate || '<empty>'} (${guard?.reason || 'unknown'})`);
            return typeof guard?.value === 'string' ? guard.value : BLOCKED_REPLY;
        } catch (error) {
            console.error('Mindcraft LoRA gateway request failed:', error.message);
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
