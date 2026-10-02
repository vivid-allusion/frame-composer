/********************************************************************************
 * Copyright (C) 2026 Vivid Allusion.
 *
 * This program and the accompanying materials are made available under the
 * terms of the Eclipse Public License v. 2.0 which is available at http://www.eclipse.org/legal/epl-2.0.
 *
 * SPDX-License-Identifier: EPL-2.0
 ********************************************************************************/

/*
 * generate-fixtures.js — rebuilds the `test-fixtures/cull-marks/` corpus.
 *
 * The corpus is shared with the Python generator (W109 plan §5.1): each case is
 * a source PNG plus the expected XMP packet bytes. The packets here are authored
 * independently of `theia-extensions/cull/src/common/cull-xmp.ts` (no import),
 * so the TS round-trip test is a real test, not a self-fulfilling one.
 *
 * Run: node test-fixtures/cull-marks/generate-fixtures.js
 */

'use strict';

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const XMP_KEYWORD = 'XML:com.adobe.xmp';
const MARKS_NS = 'https://vivid-allusion.com/ns/marks/1.0/';
const RECIPE = '{"prompt":"a detective in a dimly lit office","seed":42}';
const MARKS = { rating: 3, colors: ['green', 'red'], emoji: ['\u{1F600}'] };

const CRC_TABLE = (() => {
    const table = [];
    for (let n = 0; n < 256; n++) {
        let c = n;
        for (let k = 0; k < 8; k++) {
            c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
        }
        table[n] = c >>> 0;
    }
    return table;
})();

function crc32(bytes) {
    let crc = 0xffffffff;
    for (let i = 0; i < bytes.length; i++) {
        crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
    }
    return (crc ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
    const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
    const length = Buffer.alloc(4);
    length.writeUInt32BE(data.length, 0);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(body), 0);
    return Buffer.concat([length, body, crc]);
}

function escapeXml(value) {
    return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** The generator's packet shape (`payload_containers.py: xmp_packet`). */
function packet(recipeText, marks) {
    let siblings = '';
    let inner = '';
    if (marks) {
        if (marks.rating > 0) {
            siblings += `<xmp:Rating>${marks.rating}</xmp:Rating>`;
            inner += `<studio:rating>${marks.rating}</studio:rating>`;
        }
        if (marks.colors.length) {
            siblings += `<xmp:Label>${marks.colors[0][0].toUpperCase()}${marks.colors[0].slice(1)}</xmp:Label>`;
            inner += `<studio:colors><rdf:Bag>${marks.colors.map(c => `<rdf:li>${escapeXml(c)}</rdf:li>`).join('')}</rdf:Bag></studio:colors>`;
        }
        if (marks.emoji.length) {
            inner += `<studio:emoji><rdf:Seq>${marks.emoji.map(e => `<rdf:li>${escapeXml(e)}</rdf:li>`).join('')}</rdf:Seq></studio:emoji>`;
        }
        if (inner) {
            siblings += `<studio:marks>${inner}</studio:marks>`;
        }
    }
    const namespaces = marks ? ` xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmlns:studio="${MARKS_NS}"` : '';
    return '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        + '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        + `<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/"${namespaces}>`
        + `<dc:description>${escapeXml(recipeText)}</dc:description>${siblings}`
        + '</rdf:Description></rdf:RDF></x:xmpmeta>';
}

/** A 1x1 RGBA PNG with an optional uncompressed iTXt XMP chunk before IEND. */
function png(packetText) {
    const signature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
    const ihdr = Buffer.alloc(13);
    ihdr.writeUInt32BE(1, 0);
    ihdr.writeUInt32BE(1, 4);
    ihdr[8] = 8;
    ihdr[9] = 6;
    const parts = [signature, chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(Buffer.from([0, 255, 255, 255, 255])))];
    if (packetText !== undefined) {
        parts.push(chunk('iTXt', Buffer.concat([
            Buffer.from(XMP_KEYWORD, 'ascii'),
            Buffer.from([0, 0, 0, 0, 0]),
            Buffer.from(packetText, 'utf8')
        ])));
    }
    parts.push(chunk('IEND', Buffer.alloc(0)));
    return Buffer.concat(parts);
}

const directory = __dirname;
const recipePacket = packet(RECIPE, null);
const markedPacket = packet(RECIPE, MARKS);

const files = {
    'unmarked.png': png(undefined),
    'recipe.png': png(recipePacket),
    'recipe.expected.xmp': recipePacket,
    'marked.png': png(markedPacket),
    'marked.expected.xmp': markedPacket,
    'reinject.png': png(markedPacket),
    'reinject.expected.xmp': markedPacket,
    'README.md': [
        '# cull-marks — shared XMP fixture corpus (W109)',
        '',
        'Source PNGs plus the expected XMP packet bytes (plan §5.1). Shared by the',
        'TypeScript writer (`theia-extensions/cull/src/common/cull-xmp.ts`) and the',
        'Python generator so both agree on the packet shape.',
        '',
        '- `unmarked.png` — no XMP packet; `recipe.png` — the recipe packet, no marks.',
        '- `marked.png` — recipe + marks (rating 3, colours green/red, one emoji).',
        '- `reinject.png` — the state after a re-inject: recipe and marks both survive.',
        '- `*.expected.xmp` — the packet the reader must return for that PNG.',
        '',
        'Rebuild with `node generate-fixtures.js`.',
        ''
    ].join('\n')
};

for (const [name, data] of Object.entries(files)) {
    fs.writeFileSync(path.join(directory, name), data);
}
console.log(`cull-marks: wrote ${Object.keys(files).length} files to ${directory}`);
