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
