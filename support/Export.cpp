#include "Export.h"
#include "triton/Tools/PluginUtils.h" // For plugin:: callbacks and structs.
#include "triton/Version.h"
#include "llvm/Support/Debug.h"

#define DEBUG_TYPE "triton-ext"

///
/// Internal API.
///
namespace triton::ext::support {

using namespace mlir::triton;

// These registries are populated by extension static initializers (see
// `Export*.cpp`). When the support code is compiled *into* the same shared
// object as the extension (self-contained plugin), the relative
// initialization order of these registries and the extension's registration
// initializer is unspecified across translation units. Use construct-on-first-
// use accessors (function-local statics) so the registries are guaranteed to
// exist before any `export*` call touches them, avoiding the static
// initialization order fiasco (which otherwise crashes in `operator[]`).
using PassMap =
    std::unordered_map<std::string, std::pair<plugin::AddPassCallback,
                                              plugin::RegisterPassCallback>>;
using DialectMap =
    std::unordered_map<std::string, plugin::RegisterDialectCallback>;
using OpMap = std::unordered_map<std::string, plugin::AddOpCallback>;

static PassMap &passMap() {
  static PassMap *map = new PassMap();
  return *map;
}
static DialectMap &dialectMap() {
  static DialectMap *map = new DialectMap();
  return *map;
}
static OpMap &opMap() {
  static OpMap *map = new OpMap();
  return *map;
}

Result exportPass(const std::string passName,
                  plugin::RegisterPassCallback registerFunc,
                  plugin::AddPassCallback addFunc) {
  LLVM_DEBUG(llvm::dbgs() << "internally exporting pass: " << passName << "\n");
  passMap()[passName] = {addFunc, registerFunc};
  return TP_SUCCESS;
}

Result exportDialect(const std::string dialectName,
                     plugin::RegisterDialectCallback insertFunc) {
  LLVM_DEBUG(llvm::dbgs() << "internally exporting dialect: " << dialectName
                          << "\n");
  dialectMap()[dialectName] = insertFunc;
  return TP_SUCCESS;
}

Result exportOp(const std::string opName, plugin::AddOpCallback addFunc) {
  LLVM_DEBUG(llvm::dbgs() << "internally exporting op: " << opName << "\n");
  opMap()[opName] = addFunc;
  return TP_SUCCESS;
}
} // namespace triton::ext::support

///
/// External API.
///
using namespace triton::ext::support;
using namespace mlir::triton;

// When the support code is compiled into the extension shared object, the
// extension's name/version are available as compile definitions (see the
// extension's CMakeLists). Fall back to placeholders when built standalone
// (e.g. as a separate TritonExtensionSupport library) where they are not set.
#ifdef TRITON_EXT_NAME
static const char *PLUGIN_NAME = TOSTRING(TRITON_EXT_NAME);
#else
static const char *PLUGIN_NAME = "triton-ext-todo";
#endif
#ifdef TRITON_EXT_VERSION
static const char *VERSION = TRITON_EXT_VERSION;
#else
static const char *VERSION = "0.1.0";
#endif

TRITON_PLUGIN_API plugin::PluginInfo *tritonGetPluginInfo() {
  auto &passMap = triton::ext::support::passMap();
  auto &dialectMap = triton::ext::support::dialectMap();
  auto &opMap = triton::ext::support::opMap();
  auto passes = new plugin::PassInfo[passMap.size()];
  size_t numPasses = 0;
  for (const auto &pair : passMap) {
    const std::string &passName = pair.first;
    auto registerFunc = pair.second.second;
    auto addFunc = pair.second.first;
    passes[numPasses++] =
        plugin::PassInfo{passName.c_str(), VERSION, addFunc, registerFunc};
  }

  auto dialects = new plugin::DialectInfo[dialectMap.size()];
  size_t numDialects = 0;
  for (const auto &pair : dialectMap) {
    const std::string &dialectName = pair.first;
    auto registerFunc = pair.second;
    dialects[numDialects++] =
        plugin::DialectInfo{dialectName.c_str(), VERSION, registerFunc};
  }

  auto ops = new plugin::OpInfo[opMap.size()];
  size_t numOps = 0;
  for (const auto &pair : opMap) {
    const std::string &opName = pair.first;
    auto addFunc = pair.second;
    ops[numOps++] = plugin::OpInfo{opName.c_str(), addFunc};
  }

  auto info = new plugin::PluginInfo{TRITON_PLUGIN_API_VERSION,
                                     PLUGIN_NAME,
                                     VERSION,
                                     passes,
                                     numPasses,
                                     dialects,
                                     numDialects,
                                     ops,
                                     numOps,
                                     TRITON_VERSION};
  return info;
}

#undef DEBUG_TYPE
