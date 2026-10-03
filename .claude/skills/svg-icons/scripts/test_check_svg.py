#!/usr/bin/env python3
"""Self-test for check_svg.py (stdlib unittest). Run: python test_check_svg.py -v"""
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_svg  # noqa: E402

NS = 'xmlns="http://www.w3.org/2000/svg"'
GOOD = f'''<svg {NS} viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#4D7C90"
 stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><title>Valve</title>
<path d="M4 8h16v8H4z"/><path d="M12 8V4" stroke-width="1"/><path d="M2 2h1" fill="#F5F5F5"/></svg>'''

CASES = {
    # name: (svg text, kwargs, expected error substring or None, expected warning substring or None)
    "good": (GOOD, {}, None, None),
    "script": (f'<svg {NS} viewBox="0 0 1 1"><script>alert(1)</script></svg>', {}, "forbidden element <script>", None),
    "onload": (f'<svg {NS} viewBox="0 0 1 1" onload="x()"/>', {}, "event handler attribute onload", None),
    "js_href": (f'<svg {NS} viewBox="0 0 1 1"><a href="javascript:alert(1)"><path d="M0 0h1"/></a></svg>', {}, "executable/active URL", None),
    "js_href_spaced": (f'<svg {NS} viewBox="0 0 1 1"><a href=" java\tscript:alert(1)"/></svg>', {}, "executable/active URL", None),
    "xlink_external": (f'<svg {NS} xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1 1"><use xlink:href="http://e.com/s.svg#a"/></svg>', {}, "external reference", None),
    "use_local_ok": (f'<svg {NS} viewBox="0 0 1 1"><defs><path id="a" d="M0 0h1"/></defs><use href="#a"/></svg>', {}, None, None),
    "raster": (f'<svg {NS} viewBox="0 0 1 1"><image href="data:image/png;base64,AAAA"/></svg>', {}, "raster content", None),
    "raster_allowed": (f'<svg {NS} viewBox="0 0 1 1"><image href="data:image/png;base64,AAAA"/></svg>', {"allow_raster": True}, None, "raster content"),
    "nested_svg_uri": (f'<svg {NS} viewBox="0 0 1 1"><use href="data:image/svg+xml;base64,AAAA"/></svg>', {}, "nested SVG", None),
    "doctype": ('<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x "y">]><svg ' + NS + ' viewBox="0 0 1 1">&x;</svg>', {}, "DOCTYPE/ENTITY", None),
    "stylesheet_pi": ('<?xml-stylesheet href="http://e.com/a.css"?><svg ' + NS + ' viewBox="0 0 1 1"/>', {}, "xml-stylesheet", None),
    "no_xmlns": ('<svg viewBox="0 0 1 1"/>', {}, "not <svg> in the SVG namespace", None),
    "no_viewbox": (f'<svg {NS} width="24" height="24"/>', {}, "missing or invalid viewBox", None),
    "bad_viewbox": (f'<svg {NS} viewBox="0 0 24"/>', {}, "missing or invalid viewBox", None),
    "zero_viewbox": (f'<svg {NS} viewBox="0 0 0 24"/>', {}, "must be > 0", None),
    "style_import": (f'<svg {NS} viewBox="0 0 1 1"><style>@import url(http://e.com/a.css);</style></svg>', {}, "@import", None),
    "style_attr_url": (f'<svg {NS} viewBox="0 0 1 1"><path style="fill:url(http://e.com/p.svg#g)" d="M0 0"/></svg>', {}, "external url()", None),
    "fill_url_local_ok": (f'<svg {NS} viewBox="0 0 1 1"><path fill="url(#g)" d="M0 0"/></svg>', {}, None, None),
    "animate_href": (f'<svg {NS} viewBox="0 0 1 1"><a><set attributeName="href" to="javascript:alert(1)"/></a></svg>', {}, "animates 'href'", None),
    "foreign": (f'<svg {NS} viewBox="0 0 1 1"><foreignObject/></svg>', {}, "forbidden element <foreignObject>", None),
    "inkscape": (f'<svg {NS} xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" viewBox="0 0 1 1"><sodipodi:namedview/><metadata/></svg>', {}, None, "editor element"),
    "title_required": (f'<svg {NS} viewBox="0 0 1 1"><path d="M0 0"/></svg>', {"require_title": True}, "no <title>", None),
    "aspect_mismatch": (f'<svg {NS} viewBox="0 0 220 160" width="100" height="100"/>', {}, None, "do not match viewBox aspect"),
    "not_xml": ("<svg", {}, "not well-formed", None),
}


class CheckSvgTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_case(self, name):
        text, kwargs, err, warn = CASES[name]
        path = os.path.join(self.tmp.name, name + ".svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return check_svg.check(path, **kwargs), err, warn

    def test_cases(self):
        for name in CASES:
            with self.subTest(case=name):
                (errors, warnings, _), err, warn = self.run_case(name)
                if err is None:
                    self.assertEqual(errors, [], f"{name}: unexpected errors {errors}")
                else:
                    self.assertTrue(any(err in e for e in errors), f"{name}: {err!r} not in {errors}")
                if warn is not None:
                    self.assertTrue(any(warn in w for w in warnings), f"{name}: {warn!r} not in {warnings}")

    def test_style_report(self):
        (errors, _, info), _, _ = self.run_case("good")
        st = info["style"]
        self.assertEqual(st["stroke"], {"#4d7c90": 3})
        self.assertEqual(st["stroke-width"], {"2": 2, "1": 1})
        self.assertEqual(st["fill"], {"#f5f5f5": 1})
        self.assertEqual(st["stroke-linejoin"], {"round": 3})
        self.assertEqual(info["title"], "Valve")

    def test_cli_exit_codes(self):
        good = os.path.join(self.tmp.name, "cli_good.svg")
        bad = os.path.join(self.tmp.name, "cli_bad.svg")
        with open(good, "w", encoding="utf-8") as fh:
            fh.write(GOOD)
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write(CASES["script"][0])
        devnull = open(os.devnull, "w")
        old = sys.stdout
        sys.stdout = devnull
        try:
            self.assertEqual(check_svg.main([good]), 0)
            self.assertEqual(check_svg.main([good, bad]), 1)
            self.assertEqual(check_svg.main([os.path.join(self.tmp.name, "cli_*.svg"), "--json"]), 1)
        finally:
            sys.stdout = old
            devnull.close()
        old_err = sys.stderr
        sys.stderr = open(os.devnull, "w")
        try:
            self.assertEqual(check_svg.main([os.path.join(self.tmp.name, "nothing-*.svg")]), 2)
        finally:
            sys.stderr.close()
            sys.stderr = old_err


if __name__ == "__main__":
    unittest.main()
