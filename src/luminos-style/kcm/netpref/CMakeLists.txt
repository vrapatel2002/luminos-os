# [CHANGE: claude-code | 2026-11-08] DECISION 179
kcmutils_add_qml_kcm(kcm_luminos_netpref SOURCES netpref.cpp netpref.h INSTALL_NAMESPACE plasma/kcms/systemsettings)
target_link_libraries(kcm_luminos_netpref PRIVATE KF6::KCMUtilsQuick KF6::ConfigCore KF6::CoreAddons KF6::I18n Qt6::DBus)
set_target_properties(kcm_luminos_netpref PROPERTIES PREFIX "")
