import os, sys, unittest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import autodlg_patch as P


class CppPatchTests(unittest.TestCase):
    SRC = (
        '#include "baseDialog.hpp"\n'
        'void baseDialog::dialogShown_cb()\n'
        '{\n'
        '    try\n    {\n'
        '        //---- Enter your callback code here -----\n'
        '    }\n'
        '    catch(exception& ex)\n    {\n    }\n'
        '}\n'
    )

    def test_adds_define_include_and_hook_once(self):
        out = P.patch_cpp(self.SRC)
        self.assertEqual(out.count("AUTODLG_HOOK"), 1)
        self.assertIn("#define USER_EXIT_OR_MENU 1", out)
        self.assertIn('#include "autodlg_test.h"', out)

    def test_is_idempotent(self):
        once = P.patch_cpp(self.SRC)
        twice = P.patch_cpp(once)
        self.assertEqual(once, twice)

    def test_hook_runs_after_existing_callback_body(self):
        src = (
            '#include "baseDialog.hpp"\n'
            'void baseDialog::dialogShown_cb()\n'
            '{\n'
            '    try\n    {\n'
            '        self_init_blocks();\n'
            '    }\n'
            '    catch(exception& ex)\n    {\n    }\n'
            '}\n'
        )
        out = P.patch_cpp(src)
        self.assertLess(out.index("self_init_blocks()"),
                        out.index("AUTODLG_HOOK"))


class DlxPatchTests(unittest.TestCase):
    SRC = ('<Dialog><item id="enum0"><PropertyList>'
           '<Property id="Titles" type="utfstrings" sname="Items"/>'
           '<Property id="Titles_1" type="enum" sname="Value"/>'
           '</PropertyList></item></Dialog>')

    def test_adds_three_titles(self):
        out = P.patch_dlx(self.SRC)
        for v in ("A", "B", "C"):
            self.assertIn('value="%s"' % v, out)

    def test_adds_titles_1_options(self):
        out = P.patch_dlx(self.SRC)
        for v in ("A", "B", "C"):
            self.assertIn('name="%s"' % v, out)

    def test_is_idempotent(self):
        once = P.patch_dlx(self.SRC)
        twice = P.patch_dlx(once)
        self.assertEqual(twice.count('value="A"'), 1)
