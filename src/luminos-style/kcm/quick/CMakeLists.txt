# [CHANGE: claude-code | 2026-11-10] R25 — Luminos Quick Settings (System Settings' first page; replaces kcm_landingpage)
kcmutils_add_qml_kcm(kcm_luminos_quick SOURCES quick.cpp quick.h INSTALL_NAMESPACE plasma/kcms/systemsettings)
target_link_libraries(kcm_luminos_quick PRIVATE KF6::KCMUtilsQuick KF6::ConfigCore KF6::CoreAddons KF6::I18n Qt6::DBus Qt6::Gui)
set_target_properties(kcm_luminos_quick PROPERTIES PREFIX "")
