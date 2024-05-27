Default Alerts / Notifications
==============================

============================= ============================================
Notification Type             Use
``threshold_crossed``         Fires when a metric crosses the boundary
                              defined in the threshold value of the alert
                              settings.
``threshold_recovery``        Fires when a metric goes back within the
                              expected range.
``connection_is_working``     Fires when the connection to a device is
                              working.
``connection_is_not_working`` Fires when the connection (eg: SSH) to a
                              device stops working (eg: credentials are
                              outdated, management IP address is outdated,
                              or device is not reachable).
============================= ============================================
