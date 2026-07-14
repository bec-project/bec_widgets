import bec_widgets.widgets.containers.qt_ads as QtAds

# Default QtAds configuration
QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.eConfigFlag.FocusHighlighting, True)
QtAds.CDockManager.setConfigFlag(
    QtAds.CDockManager.eConfigFlag.RetainTabSizeWhenCloseButtonHidden, True
)
