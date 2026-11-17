Paste each file into ZeptoMail using the HTML / source editor, not the visual editor.
The visual editor splits tables and inserts line breaks.

File                                          Env key
zeptomail-abandoned-cart-reminder.html        ZEPTOMAIL_CART_REMINDER_TEMPLATE_KEY
zeptomail-order-confirmation.html             ZEPTOMAIL_ORDER_CONFIRMATION_TEMPLATE_KEY
zeptomail-otp-activation.html                 ZEPTOMAIL_OTP_TEMPLATE_KEY
zeptomail-otp-login.html                      ZEPTOMAIL_OTP_LOGIN_TEMPLATE_KEY
zeptomail-password-reset.html                 ZEPTOMAIL_PASSWORD_RESET_TEMPLATE_KEY

On the cart template, set the cart_items_html merge field to raw HTML.
Keep {{cart_items_html}} inside the items table, directly under the Product / Qty / Price header.
