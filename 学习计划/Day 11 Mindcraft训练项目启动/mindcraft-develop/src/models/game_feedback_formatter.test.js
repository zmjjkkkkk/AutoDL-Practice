import assert from 'node:assert/strict';

import {formatQueryFeedback} from './game_feedback_formatter.js';


assert.equal(
    formatQueryFeedback('!inventory', 'INVENTORY\n- oak_log: 4\n- apple: 1\nWEARING: \nNothing'),
    'Inventory: 4 oak logs, 1 apple; no armor equipped.',
);

assert.equal(
    formatQueryFeedback('!inventory', 'INVENTORY: Nothing\nWEARING: \nNothing'),
    'Inventory: empty; no armor equipped.',
);

assert.equal(
    formatQueryFeedback('!inventory', 'INVENTORY\n- oak_log: 4\n- apple: 1\n- cobblestone: 9\n- iron_ingot: 6\nWEARING: \nNothing'),
    'Inventory: 9 cobblestones, 6 iron ingots, 4 oak logs, plus 1 other item types; no armor equipped.',
);

assert.equal(
    formatQueryFeedback('!nearbyBlocks', 'NEARBY_BLOCKS\n- oak_log\n- grass_block\n- First Solid Block Above Head: stone'),
    'Nearby blocks include oak log, grass block. The first solid block above my head is stone.',
);

assert.equal(
    formatQueryFeedback('!stats', 'STATS\n- Health: 20 / 20\n- Hunger: 18 / 20\n- Biome: forest\n- Weather: Clear\n- Time: Night\n- Current Action: Idle'),
    'It is night in forest with clear weather. I have 20 / 20 health, 18 / 20 hunger, currently idle.',
);

assert.equal(formatQueryFeedback('!inventory', 'unrecognized result'), 'unrecognized result');

console.log('Game feedback formatter tests passed.');
