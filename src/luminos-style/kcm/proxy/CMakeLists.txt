# [CHANGE: claude-code | 2026-11-08] DECISION 179 (kcmutils hard-codes the ui/ folder next to this file)
kcmutils_add_qml_kcm(kcm_luminos_proxy SOURCES proxy.cpp proxy.h INSTALL_NAMESPACE plasma/kcms/systemsettings)
target_link_libraries(kcm_luminos_proxy PRIVATE KF6::KCMUtilsQuick KF6::ConfigCore KF6::CoreAddons KF6::I18n Qt6::DBus)
set_target_properties(kcm_luminos_proxy PROPERTIES PREFIX "") # plugin id = file name
