cmake_minimum_required(VERSION 3.20)
project(kcm_luminos_hive VERSION 1.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(ECM 6.0.0 REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})

include(KDEInstallDirs6)
include(KDECMakeSettings)
include(KDECompilerSettings NO_POLICY_SCOPE)

find_package(Qt6 REQUIRED COMPONENTS Core Quick Qml)
find_package(KF6 REQUIRED COMPONENTS CoreAddons I18n KCMUtils)

kcmutils_add_qml_kcm(kcm_luminos_hive
    SOURCES kcm_luminos_hive.cpp
)

target_link_libraries(kcm_luminos_hive
    KF6::KCMUtilsQuick
    KF6::CoreAddons
    Qt6::Core
    Qt6::Quick
)
