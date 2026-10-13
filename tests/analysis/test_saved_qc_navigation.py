# SPDX-License-Identifier: GPL-3.0-only
"""Execute the shipped navigation script; native layout/keyboard gates are separate."""

from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser

from test_saved_qc_comparison_view import fixture, model, raw, view

NODE = shutil.which("node")
# This bounded DOM adapter executes the actual inline script. It is not a browser.
DRIVER = r"""
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
let focused = null;
const downloads = [], blobs = new Map();
class Element {
  constructor(tag, id = '') {
    this.tagName = tag; this.id = id; this.children = []; this.dataset = {};
    this.attributes = {}; this.listeners = {}; this.textContent = '';
    this.disabled = false; this.hidden = false; this.value = ''; this.parent = null;
    this.classList = {toggle() {}};
  }
  append(...elements) {
    for (const child of elements) {
      if (child.tagName === 'fragment') this.append(...child.children);
      else {child.parent = this; this.children.push(child);}
    }
  }
  replaceChildren(...elements) {this.children = []; this.append(...elements);}
  setAttribute(key, value) {this.attributes[key] = String(value);}
  addEventListener(type, action) {this.listeners[type] = action;}
  querySelectorAll(selector) {
    const matches = child => selector === 'button[data-index]'
      ? child.tagName === 'button' && child.dataset.index !== undefined
      : child.tagName === selector;
    return this.children.flatMap(child => [
      ...(matches(child) ? [child] : []), ...child.querySelectorAll(selector)
    ]);
  }
  closest(tag) {return this.tagName === tag ? this : this.parent?.closest(tag);}
  focus() {focused = this.id;}
  remove() {if (this.parent) this.parent.children = this.parent.children.filter(x => x !== this);}
  click() {
    if (this.disabled) return;
    if (this.tagName === 'a') downloads.push({name: this.download, blob: blobs.get(this.href)});
    if (this.listeners.click) this.listeners.click();
  }
}
const elements = new Map(input.elements.map(([tag, attrs]) => {
  const element = new Element(tag, attrs.id);
  element.disabled = Object.hasOwn(attrs, 'disabled');
  element.hidden = Object.hasOwn(attrs, 'hidden');
  if (attrs.id === 'kind-filter') element.value = 'all';
  if (attrs.id === 'qc-data') element.textContent = input.encoded;
  return [attrs.id, element];
}));
const get = id => elements.get(id) || null;
const document = {getElementById: get, createElement: tag => new Element(tag),
  createDocumentFragment: () => new Element('fragment'), body: new Element('body')};
vm.runInNewContext(input.script, {document, atob, Uint8Array, Blob,
  setTimeout: action => action(), URL: {
    createObjectURL(blob) {const url = 'blob:' + blobs.size; blobs.set(url, blob); return url;},
    revokeObjectURL() {}
  }
}, {timeout: 2000});
assert.equal(document.body.dataset.ready, 'true', 'page initialized');
function snapshot() {
  const buttons = get('rows').querySelectorAll('button[data-index]');
  return {
    previous: get('previous-change')?.disabled ?? null,
    next: get('next-change')?.disabled ?? null,
    position: get('change-position')?.textContent ?? null,
    title: get('detail-title').textContent,
    pointer: get('detail-pointer').textContent,
    before: [get('before-type').textContent, get('before-value').textContent],
    after: [get('after-type').textContent, get('after-value').textContent],
    pressed: buttons.filter(b => b.attributes['aria-pressed'] === 'true')
      .map(b => Number(b.dataset.index)),
    rowIds: buttons.map(b => Number(b.dataset.index)),
    page: get('page-status').textContent, focus: focused
  };
}
const states = [snapshot()];
for (const action of input.actions) {
  if (action.inspect !== undefined) {
    const button = get('rows').querySelectorAll('button[data-index]')
      .find(b => Number(b.dataset.index) === action.inspect);
    assert.ok(button, 'selected original difference is on this page'); button.click();
  } else if (action.filter) {
    const element = get(action.filter[0]); element.value = action.filter[1];
    element.listeners[action.filter[0] === 'pointer-filter' ? 'input' : 'change']();
  } else {
    const button = get(action.click); assert.ok(button, 'control exists: ' + action.click);
    button.click();
  }
  states.push(snapshot());
}
for (const id of ['download-first', 'download-second', 'download-comparison']) get(id).click();
Promise.all(downloads.map(async item => ({name: item.name,
  bytes: Buffer.from(await item.blob.arrayBuffer()).toString('base64')})))
  .then(downloads => process.stdout.write(JSON.stringify({states, downloads})))
  .catch(error => {console.error(error); process.exitCode = 1;});
"""


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.elements.append((tag, attrs))


def typed_pair():
    return raw(fixture(extension={
        "a": False, "b": 1, "c": -0.0, "d": 9007199254740993,
        "e": None, "literal/~": "<b>& Ω\n", "gone": None,
    })), raw(fixture(extension={
        "a": 0, "b": 1.0, "c": 0.0, "d": 9007199254740994,
        "e": [False], "literal/~": "<i>λ\t", "new": None,
    }))


def many_pair():
    return raw(fixture(extension={f"row{i:03}": i for i in range(61)})), raw(
        fixture(extension={f"row{i:03}": i + 1 for i in range(61)})
    )


@unittest.skipUnless(NODE, "Node is required to execute the shipped inline UI")
class SavedQCNavigationTests(unittest.TestCase):
    def run_page(self, first, second, actions=()):
        html = view.render_comparison_html(first, second, first_name="literal Ω.json")
        data = model(html)
        script, = re.findall(r"<script>\s*(.*?)</script>", html, re.S)
        encoded, = re.findall(r'type="application/octet-stream">([^<]+)</script>', html)
        payload = {"elements": Elements(html).elements, "script": script,
                   "encoded": encoded, "actions": actions}
        result = subprocess.run([NODE, "-e", DRIVER], input=json.dumps(payload),
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        output = json.loads(result.stdout)
        self.assertEqual([base64.b64decode(d["bytes"]) for d in output["downloads"]],
                         [first, second, base64.b64decode(data["comparisonBase64"])])
        self.assertEqual([d["name"] for d in output["downloads"]],
                         ["literal Ω.json", "second-qc.json", "qc-comparison.json"])
        return output["states"], data["rows"]

    def assert_clear(self, state):
        self.assertEqual((state["previous"], state["next"]), (True, True))
        self.assertEqual(state["position"], "")
        self.assertEqual(state["title"], "Select a difference")
        self.assertEqual((state["pointer"], state["before"], state["after"]),
                         ("", ["", ""], ["", ""]))
        self.assertEqual(state["pressed"], [])

    def assert_row(self, state, row):
        self.assertEqual(state["pressed"], [row["index"]])
        self.assertEqual(state["title"], f"Difference {row['index'] + 1}")
        self.assertEqual(state["pointer"], row["pointer"])
        for side in ("before", "after"):
            self.assertEqual(state[side], [row[side]["type"], row[side]["text"]])
        self.assertEqual(state["focus"], "detail-title")

    def test_initial_equal_and_nonempty_have_no_selection(self):
        for pair in (typed_pair(), (raw(fixture()), raw(fixture()))):
            with self.subTest(equal=pair[0] == pair[1]):
                self.assert_clear(self.run_page(*pair)[0][0])

    def test_adjacent_selection_and_endpoint_no_wrap(self):
        states, rows = self.run_page(*typed_pair(), [
            {"inspect": 0}, {"click": "previous-change"}, {"click": "next-change"},
            {"inspect": 7}, {"click": "next-change"}, {"click": "previous-change"},
        ])
        for state, index in zip(states[1:], (0, 0, 1, 7, 7, 6), strict=True):
            self.assert_row(state, rows[index])
        self.assertEqual((states[1]["previous"], states[1]["next"]), (True, False))
        self.assertEqual((states[4]["previous"], states[4]["next"]), (False, True))
        self.assertEqual(states[-1]["position"], "Matching change 7 of 8")

    def test_complete_filtered_order_retains_original_indices(self):
        states, rows = self.run_page(*typed_pair(), [
            {"filter": ["kind-filter", "changed"]}, {"inspect": 4},
            {"click": "next-change"}, {"click": "previous-change"},
        ])
        self.assertEqual(states[1]["rowIds"], [0, 1, 2, 3, 4, 6])
        self.assert_clear(states[1])
        self.assert_row(states[3], rows[6])
        self.assertEqual(states[3]["position"], "Matching change 6 of 6")
        self.assert_row(states[4], rows[4])

    def test_crosses_fiftieth_row_in_both_directions(self):
        states, rows = self.run_page(*many_pair(), [
            {"inspect": 49}, {"click": "next-change"}, {"click": "previous-change"},
        ])
        self.assert_row(states[2], rows[50])
        self.assertEqual(states[2]["page"], "Page 2 of 2")
        self.assertEqual(states[2]["rowIds"], list(range(50, 61)))
        self.assertEqual(states[2]["position"], "Matching change 51 of 61")
        self.assert_row(states[3], rows[49])
        self.assertEqual(states[3]["page"], "Page 1 of 2")
        self.assertEqual(states[3]["rowIds"], list(range(50)))

    def test_single_match_and_no_hits_disable_navigation(self):
        states, rows = self.run_page(*typed_pair(), [
            {"filter": ["kind-filter", "added"]}, {"inspect": 7},
            {"click": "next-change"}, {"filter": ["pointer-filter", "no such pointer"]},
        ])
        self.assert_row(states[2], rows[7])
        self.assertEqual(states[2]["position"], "Matching change 1 of 1")
        self.assertEqual((states[2]["previous"], states[2]["next"]), (True, True))
        self.assertEqual(states[3]["pointer"], states[2]["pointer"])
        self.assert_clear(states[4])
        self.assertEqual(states[4]["rowIds"], [])

    def test_manual_pages_both_filters_and_reset_clear_selection(self):
        states, _ = self.run_page(*many_pair(), [
            {"inspect": 49}, {"click": "next-page"}, {"inspect": 50},
            {"click": "prev-page"}, {"inspect": 0},
            {"filter": ["kind-filter", "changed"]}, {"inspect": 0},
            {"filter": ["pointer-filter", "row00"]}, {"inspect": 1},
            {"click": "reset"},
        ])
        for index in (2, 4, 6, 8, 10):
            self.assert_clear(states[index])
        self.assertEqual(states[-1]["rowIds"], list(range(50)))

    def test_full_typed_text_survives_navigation(self):
        states, rows = self.run_page(*typed_pair(), [
            {"inspect": 0}, *({"click": "next-change"} for _ in range(7)),
        ])
        for state, row in zip(states[1:], rows, strict=True):
            self.assert_row(state, row)
        self.assertEqual(states[3]["before"], ["float", "-0.0"])
        self.assertEqual(states[4]["before"], ["integer", "9007199254740993"])
        self.assertEqual(states[6]["after"], ["absent", "(absent)"])
        self.assertEqual(states[7]["pointer"], "/extension/literal~1~0")
        self.assertEqual(states[7]["before"][1], '"<b>& \\u03a9\\n"')

    def test_original_downloads_and_existing_selection_remain_complete(self):
        states, rows = self.run_page(*typed_pair(), [
            {"inspect": 3}, {"filter": ["kind-filter", "added"]},
        ])
        self.assert_row(states[1], rows[3])
        self.assertEqual(states[-1]["rowIds"], [7])


if __name__ == "__main__":
    unittest.main()
