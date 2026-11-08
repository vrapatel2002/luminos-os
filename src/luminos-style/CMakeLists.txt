# [CHANGE: claude-code | 2026-11-08] Luminos style tuner (DECISION 176) — live style values for the forked KDE QML.
cmake_minimum_required(VERSION 3.20)
project(luminos-style VERSION 1.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)
find_package(Qt6 6.5 REQUIRED COMPONENTS Core Qml)
qt_standard_project_setup(REQUIRES 6.5)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
qt_add_library(luminosstyleplugin MODULE)  # backing target == plugin: one self-contained .so
qt_add_qml_module(luminosstyleplugin
    URI org.luminos.style
    VERSION 1.0
    PLUGIN_TARGET luminosstyleplugin
    SOURCES style.h style.cpp
    OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/org/luminos/style
)
target_link_libraries(luminosstyleplugin PRIVATE Qt6::Core Qt6::Qml)
include(GNUInstallDirs)
set(QMLDIR_INSTALL ${CMAKE_INSTALL_LIBDIR}/qt6/qml/org/luminos/style)
install(TARGETS luminosstyleplugin LIBRARY DESTINATION ${QMLDIR_INSTALL})
install(FILES ${CMAKE_BINARY_DIR}/org/luminos/style/qmldir
              ${CMAKE_BINARY_DIR}/org/luminos/style/luminosstyleplugin.qmltypes
        DESTINATION ${QMLDIR_INSTALL})

# [CHANGE: claude-code | 2026-11-08] DECISION 178 — org.luminos.network: the Wi-Fi page's settings helper.
# Its own plugin, so only that page loads NetworkManagerQt (every other QML app loads just org.luminos.style).
find_package(KF6NetworkManagerQt REQUIRED)
find_package(Qt6 REQUIRED COMPONENTS DBus)
qt_add_library(luminosnetworkplugin MODULE)
qt_add_qml_module(luminosnetworkplugin
    URI org.luminos.network
    VERSION 1.0
    PLUGIN_TARGET luminosnetworkplugin
    SOURCES network/networkconnection.h network/networkconnection.cpp
    OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/org/luminos/network
)
target_include_directories(luminosnetworkplugin PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/network)
target_link_libraries(luminosnetworkplugin PRIVATE Qt6::Core Qt6::Qml Qt6::DBus KF6::NetworkManagerQt)
set(NETDIR_INSTALL ${CMAKE_INSTALL_LIBDIR}/qt6/qml/org/luminos/network)
install(TARGETS luminosnetworkplugin LIBRARY DESTINATION ${NETDIR_INSTALL})
install(FILES ${CMAKE_BINARY_DIR}/org/luminos/network/qmldir
              ${CMAKE_BINARY_DIR}/org/luminos/network/luminosnetworkplugin.qmltypes
        DESTINATION ${NETDIR_INSTALL})

# [CHANGE: claude-code | 2026-11-08] DECISION 179 — our Proxy and Connection Preferences pages (QML KCMs).
# The systemsettings fork hides kio-extras' kcm_proxy / kcm_netpref when these two are installed.
set(BUILD_SHARED_LIBS ON) # kcoreaddons_add_plugin makes static plugins otherwise
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib) # kcoreaddons_add_plugin requires it
set(KDE_INSTALL_PLUGINDIR ${CMAKE_INSTALL_LIBDIR}/qt6/plugins) # where KCM plugins go (no KDEInstallDirs here)
find_package(ECM REQUIRED NO_MODULE)
list(APPEND CMAKE_MODULE_PATH ${ECM_MODULE_PATH})
find_package(KF6 REQUIRED COMPONENTS KCMUtils Config CoreAddons I18n)
add_subdirectory(kcm/proxy)
add_subdirectory(kcm/netpref)
