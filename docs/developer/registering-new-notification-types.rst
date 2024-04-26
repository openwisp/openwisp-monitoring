Registering new notification types
----------------------------------

.. include:: /partials/developers-docs-warning.rst

You can define your own notification types using ``register_notification_type`` function from OpenWISP
Notifications. For more information, see the relevant `openwisp-notifications section about registering notification types
<https://github.com/openwisp/openwisp-notifications#registering--unregistering-notification-types>`_.

Once a new notification type is registered, you have to use the `"notify" signal provided in
openwisp-notifications <https://github.com/openwisp/openwisp-notifications#sending-notifications>`_
to send notifications for this type.
