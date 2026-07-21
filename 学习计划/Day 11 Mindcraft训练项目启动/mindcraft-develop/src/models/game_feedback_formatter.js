/* Deterministic presentation helpers for read-only Mindcraft query feedback. */

const MAX_LISTED_ITEMS = 3;


function displayName(value) {
    return value.replaceAll('_', ' ');
}


function bulletLines(text) {
    return text
        .split('\n')
        .map(line => line.trim().replace(/^[\\-]+\s*/, ''))
        .filter(Boolean);
}


function summarizeList(items, emptyMessage) {
    if (!items.length) return emptyMessage;
    const shown = items.slice(0, MAX_LISTED_ITEMS);
    const remaining = items.length - shown.length;
    const joined = shown.join(', ');
    return remaining > 0 ? `${joined}, plus ${remaining} other item types` : joined;
}


function formatItemCount(itemName, count) {
    const name = displayName(itemName);
    return `${count} ${count === 1 ? name : `${name}s`}`;
}


function formatInventory(text) {
    const lines = bulletLines(text);
    const wearingIndex = lines.findIndex(line => line.startsWith('WEARING:'));
    const itemLines = lines
        .slice(0, wearingIndex === -1 ? lines.length : wearingIndex)
        .filter(line => line !== 'INVENTORY' && !line.startsWith('INVENTORY:'));
    const items = itemLines
        .map(line => {
            const match = line.match(/^([a-z0-9_]+):\s*(\d+)$/i);
            return match ? {name: match[1], count: Number(match[2])} : null;
        })
        .filter(Boolean)
        .sort((left, right) => right.count - left.count)
        .map(item => formatItemCount(item.name, item.count));

    const wearingLines = wearingIndex === -1 ? [] : lines.slice(wearingIndex + 1);
    const armor = wearingLines
        .filter(line => /^(Head|Torso|Legs|Feet):/i.test(line))
        .map(line => displayName(line.replace(/^(Head|Torso|Legs|Feet):\s*/i, '')));

    const armorPhrase = armor.length
        ? `equipped: ${armor.join(', ')}`
        : 'no armor equipped';
    return `Inventory: ${summarizeList(items, 'empty')}; ${armorPhrase}.`;
}


function formatNearbyBlocks(text) {
    const lines = bulletLines(text).filter(line => line !== 'NEARBY_BLOCKS');
    if (lines.some(line => line.toLowerCase() === 'nearby_blocks: none')) {
        return 'I could not find nearby blocks to report.';
    }

    const abovePrefix = 'First Solid Block Above Head:';
    const above = lines.find(line => line.startsWith(abovePrefix));
    const blocks = lines
        .filter(line => !line.startsWith(abovePrefix))
        .map(displayName);
    const blockSentence = `Nearby blocks include ${summarizeList(blocks, 'no identified blocks')}.`;
    if (!above) return blockSentence;
    return `${blockSentence} The first solid block above my head is ${displayName(above.slice(abovePrefix.length).trim())}.`;
}


function formatStats(text) {
    const details = new Map();
    for (const line of bulletLines(text)) {
        const match = line.match(/^([A-Za-z ]+):\s*(.+)$/);
        if (match) details.set(match[1].trim().toLowerCase(), match[2].trim());
    }

    const fragments = [];
    if (details.has('time')) fragments.push(`It is ${details.get('time').toLowerCase()}`);
    if (details.has('biome')) fragments.push(`in ${displayName(details.get('biome'))}`);
    if (details.has('weather')) fragments.push(`with ${details.get('weather').toLowerCase()} weather`);
    const firstSentence = fragments.length ? `${fragments.join(' ')}.` : 'I could not read the current world status.';

    const condition = [];
    if (details.has('health')) condition.push(`${details.get('health')} health`);
    if (details.has('hunger')) condition.push(`${details.get('hunger')} hunger`);
    if (details.has('current action')) condition.push(`currently ${details.get('current action').toLowerCase()}`);
    return condition.length ? `${firstSentence} I have ${condition.join(', ')}.` : firstSentence;
}


export function formatQueryFeedback(commandName, text) {
    if (typeof text !== 'string' || !text.trim()) return text;
    if (commandName === '!inventory' && text.includes('INVENTORY')) return formatInventory(text);
    if (commandName === '!nearbyBlocks' && text.includes('NEARBY_BLOCKS')) return formatNearbyBlocks(text);
    if (commandName === '!stats' && text.includes('STATS')) return formatStats(text);
    return text;
}
