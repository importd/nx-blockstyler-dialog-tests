#ifndef AUTODLG_TEST_H_INCLUDED
#define AUTODLG_TEST_H_INCLUDED

/* Header-only test hook for NX 10 Block Styler dialogs.
 *
 * The dialog's dialogShown_cb calls:
 *     AUTODLG_HOOK(theDialog, "selection0", "enum0", "linear_dim0");
 * guarded by #ifdef AUTODLG_TEST (autodlg_patch.py inserts it).
 *
 * When AUTODLG_CASE is set, collect() reads the case, injects via the public
 * PropertyList API, reads values back, and finish() writes the result and
 * closes the dialog with WM_CLOSE. Production builds define no AUTODLG_TEST,
 * so AUTODLG_HOOK is a no-op and none of this code is compiled.
 */

#ifdef AUTODLG_TEST

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif

#include <windows.h>
#pragma comment(lib, "user32.lib")
/* windows.h turns CreateDialog and CALLBACK into macros; the generated dialog
 * code uses NXOpen::UI::CreateDialog and #if CALLBACK. Restore both names. */
#undef CreateDialog
#undef CreateDialogA
#undef CreateDialogW
#undef CALLBACK
#include <process.h>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include <NXOpen/BlockStyler_BlockDialog.hxx>
#include <NXOpen/BlockStyler_PropertyList.hxx>
#include <NXOpen/Body.hxx>
#include <NXOpen/BodyCollection.hxx>
#include <NXOpen/NXException.hxx>
#include <NXOpen/Part.hxx>
#include <NXOpen/PartCollection.hxx>
#include <NXOpen/Session.hxx>

namespace autodlg {

struct Context {
    std::map<std::string, std::string> sets;
    std::map<std::string, std::string> got;
    bool apply;
    int apply_rc;
    std::string error;
    std::string out_path;
    int timeout_ms;
    bool no_close;
    bool kill_on_hang;
};

inline std::string trim(const std::string &s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

inline std::string one_line(const std::string &s) {
    std::string out = s;
    for (size_t i = 0; i < out.size(); ++i) {
        if (out[i] == '\r' || out[i] == '\n') out[i] = ' ';
    }
    return out;
}

inline bool env_flag(const char *name, bool def) {
    const char *v = getenv(name);
    if (v == NULL) return def;
    return std::string(v) == "1";
}

inline int env_int(const char *name, int def) {
    const char *v = getenv(name);
    if (v == NULL) return def;
    return atoi(v);
}

struct ChildSearch {
    const char *text;
    int mode;  /* 0 = window title, 1 = class-name prefix */
    bool found;
};

inline BOOL __stdcall enum_child_proc(HWND h, LPARAM lp) {
    ChildSearch *s = reinterpret_cast<ChildSearch *>(lp);
    if (s->mode == 0) {
        char title[256] = {0};
        GetWindowTextA(h, title, sizeof(title));
        if (strcmp(title, s->text) == 0) {
            s->found = true;
            return FALSE;
        }
    } else {
        char cls[256] = {0};
        GetClassNameA(h, cls, sizeof(cls));
        if (strncmp(cls, s->text, strlen(s->text)) == 0) {
            s->found = true;
            return FALSE;
        }
    }
    return TRUE;
}

inline bool has_child(HWND parent, const char *text, int mode) {
    ChildSearch s;
    s.text = text;
    s.mode = mode;
    s.found = false;
    EnumChildWindows(parent, enum_child_proc, reinterpret_cast<LPARAM>(&s));
    return s.found;
}

inline BOOL __stdcall enum_window_proc(HWND h, LPARAM lp) {
    DWORD pid = 0;
    GetWindowThreadProcessId(h, &pid);
    if (pid != GetCurrentProcessId()) return TRUE;
    if (!IsWindowVisible(h)) return TRUE;
    char cls[256] = {0};
    GetClassNameA(h, cls, sizeof(cls));
    if (strcmp(cls, "#32770") != 0) return TRUE;
    /* UGS::BlockStyler::DialogCreator is the child window's *title*; its class
     * is Afx:... . Match either, so a changed title still finds the dialog. */
    if (!has_child(h, "UGS::BlockStyler::DialogCreator", 0) &&
        !has_child(h, "Afx:", 1)) {
        return TRUE;
    }
    *reinterpret_cast<HWND *>(lp) = h;
    return FALSE;
}

inline HWND find_dialog() {
    HWND found = NULL;
    EnumWindows(enum_window_proc, reinterpret_cast<LPARAM>(&found));
    return found;
}

inline bool post_close() {
    HWND h = find_dialog();
    if (h == NULL) return false;
    PostMessageW(h, WM_CLOSE, 0, 0);
    return true;
}

struct ThreadState {
    int timeout_ms;
    bool no_close;
    bool kill_on_hang;
};

inline unsigned __stdcall close_thread(void *param) {
    ThreadState *st = reinterpret_cast<ThreadState *>(param);
    if (st->no_close) return 0;
    /* The dialog's child windows appear slightly after dialogShown_cb; retry
     * until find_dialog() can see it. */
    for (int i = 0; i < 8; ++i) {
        Sleep(i == 0 ? 600 : 400);
        if (post_close()) return 0;
    }
    return 0;
}

inline unsigned __stdcall watch_thread(void *param) {
    ThreadState *st = reinterpret_cast<ThreadState *>(param);
    Sleep(static_cast<DWORD>(st->timeout_ms));
    if (st->no_close) {
        if (find_dialog() != NULL && st->kill_on_hang)
            TerminateProcess(GetCurrentProcess(), 3);
        return 0;
    }
    if (find_dialog() == NULL) return 0;
    post_close();
    Sleep(1000);
    if (find_dialog() != NULL && st->kill_on_hang)
        TerminateProcess(GetCurrentProcess(), 3);
    return 0;
}

inline void write_result(Context *ctx) {
    if (ctx->out_path.empty()) return;
    std::ofstream f(ctx->out_path.c_str(), std::ios::out | std::ios::trunc);
    if (!f) return;
    f << "shown=1\n";
    f << "hook_ran=1\n";
    f << "close_attempted=" << (ctx->no_close ? 0 : 1) << "\n";
    if (ctx->apply) f << "apply_rc=" << ctx->apply_rc << "\n";
    else f << "apply_rc=\n";
    f << "error=" << one_line(ctx->error) << "\n";
    for (std::map<std::string, std::string>::const_iterator it = ctx->got.begin();
         it != ctx->got.end(); ++it) {
        f << "got." << it->first << "=" << it->second << "\n";
    }
    f.flush();
    f.close();
}

inline bool collect(NXOpen::BlockStyler::BlockDialog *dlg,
                    const char *const *ids, int n, Context *ctx) {
    const char *case_path = getenv("AUTODLG_CASE");
    if (case_path == NULL) return false;

    ctx->apply = false;
    ctx->apply_rc = 0;
    ctx->timeout_ms = env_int("AUTODLG_TIMEOUT_MS", 8000);
    ctx->no_close = env_flag("AUTODLG_NO_CLOSE", false);
    ctx->kill_on_hang = env_flag("AUTODLG_KILL_ON_HANG", true);
    const char *out = getenv("AUTODLG_OUT");
    if (out != NULL) ctx->out_path = out;

    std::ifstream case_file(case_path);
    std::string line;
    while (std::getline(case_file, line)) {
        line = trim(line);
        if (line.empty()) continue;
        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        std::string key = trim(line.substr(0, eq));
        std::string val = trim(line.substr(eq + 1));
        if (key == "apply") {
            ctx->apply = (val == "1");
        } else if (key.size() > 4 && key.substr(0, 4) == "set.") {
            ctx->sets[key.substr(4)] = val;
        }
    }

    for (int i = 0; i < n; ++i) {
        std::string id = ids[i];
        try {
            NXOpen::BlockStyler::PropertyList *pl =
                dlg->GetBlockProperties(id.c_str());
            if (pl == NULL) {
                ctx->error += "null:" + id + ";";
                continue;
            }

            bool is_selection = false;
            try {
                NXOpen::BlockStyler::PropertyList::PropertyType t =
                    pl->GetPropertyType("SelectedObjects");
                is_selection =
                    (t == NXOpen::BlockStyler::PropertyList::PropertyTypeTaggedObjectVector);
            } catch (...) {
                is_selection = false;
            }

            if (is_selection) {
                if (ctx->sets.find(id) != ctx->sets.end()) {
                    std::string v = ctx->sets[id];
                    if (v != "first_body") {
                        ctx->error += "unsupported:selection value;";
                    } else {
                        NXOpen::Part *part =
                            NXOpen::Session::GetSession()->Parts()->Work();
                        NXOpen::Body *body = NULL;
                        if (part != NULL) {
                            NXOpen::BodyCollection *bodies = part->Bodies();
                            for (NXOpen::BodyCollection::iterator it = bodies->begin();
                                 it != bodies->end(); ++it) {
                                body = *it;
                                break;
                            }
                        }
                        if (body == NULL) {
                            ctx->error += "no body;";
                        } else {
                            std::vector<NXOpen::TaggedObject *> objs;
                            objs.push_back(body);
                            pl->SetTaggedObjectVector("SelectedObjects", objs);
                        }
                    }
                }
                std::vector<NXOpen::TaggedObject *> objs =
                    pl->GetTaggedObjectVector("SelectedObjects");
                std::ostringstream os;
                os << objs.size();
                ctx->got[id] = os.str();
                continue;
            }

            NXOpen::BlockStyler::PropertyList::PropertyType vt =
                pl->GetPropertyType("Value");
            if (vt == NXOpen::BlockStyler::PropertyList::PropertyTypeDouble) {
                if (ctx->sets.find(id) != ctx->sets.end()) {
                    pl->SetDouble("Value", atof(ctx->sets[id].c_str()));
                }
                std::ostringstream os;
                os << pl->GetDouble("Value");
                ctx->got[id] = os.str();
            } else if (vt == NXOpen::BlockStyler::PropertyList::PropertyTypeEnum ||
                       vt == NXOpen::BlockStyler::PropertyList::PropertyTypeInteger) {
                if (ctx->sets.find(id) != ctx->sets.end()) {
                    pl->SetEnum("Value", atoi(ctx->sets[id].c_str()));
                }
                std::ostringstream os;
                os << pl->GetEnum("Value");
                ctx->got[id] = os.str();
            } else {
                ctx->error += "unsupported:" + id + ";";
            }
        } catch (std::exception &ex) {
            ctx->error += "block:" + id + ":" + ex.what() + ";";
        } catch (...) {
            ctx->error += "block:" + id + ":unknown;";
        }
    }
    return true;
}

inline void finish(Context *ctx) {
    write_result(ctx);
    ThreadState *st = new ThreadState();
    st->timeout_ms = ctx->timeout_ms;
    st->no_close = ctx->no_close;
    st->kill_on_hang = ctx->kill_on_hang;
    _beginthreadex(NULL, 0, close_thread, st, 0, NULL);
    _beginthreadex(NULL, 0, watch_thread, st, 0, NULL);
}

}  // namespace autodlg

#define AUTODLG_HOOK(dlg, ...) do { \
    const char* _autodlg_ids[] = {__VA_ARGS__}; \
    autodlg::Context _autodlg_ctx; \
    if (autodlg::collect(dlg, _autodlg_ids, \
            (int)(sizeof(_autodlg_ids)/sizeof(_autodlg_ids[0])), &_autodlg_ctx)) { \
        if (_autodlg_ctx.apply) { \
            try { _autodlg_ctx.apply_rc = apply_cb(); } \
            catch (std::exception& ex) { \
                _autodlg_ctx.error += std::string("apply:") + ex.what() + ";"; \
                _autodlg_ctx.apply_rc = -1; \
            } catch (...) { \
                _autodlg_ctx.error += "apply:unknown;"; \
                _autodlg_ctx.apply_rc = -1; \
            } \
        } \
        autodlg::finish(&_autodlg_ctx); \
    } \
} while (0)

#else
#define AUTODLG_HOOK(...) ((void)0)
#endif

#endif  // AUTODLG_TEST_H_INCLUDED
