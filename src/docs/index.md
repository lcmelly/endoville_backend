---
title: Home
icon: lucide/house
---

<img class="endoville-home-logo endoville-home-logo--light" src="assets/images/logo_white.png#only-light" alt="Endoville">
<img class="endoville-home-logo endoville-home-logo--dark" src="assets/images/logo_dark.png#only-dark" alt="Endoville Health">

# Endoville Backend

This is the API for the Endoville store. You use it to create accounts, browse products and posts, keep a cart, place orders, take payment, and track a shipment.

You can read the catalog and the blog without signing in. For anything else, sign in first and send the access token with the request. The [get started](guides/getting-started.md) guide walks through that once.

## Start here

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } __Getting started__

    ---

    Create an account, sign in, and call your first protected route.

    [:octicons-arrow-right-24: Open the guide](guides/getting-started.md)

-   :material-sitemap:{ .lg .middle } __Architecture__

    ---

    A plain-language map of accounts, the shelf, checkout, and shipping.

    [:octicons-arrow-right-24: Read the map](architecture.md)

</div>

## Accounts

<div class="grid cards" markdown>

-   :material-account-plus:{ .lg .middle } __Registration__

    ---

    Create an account. We email a short code so you can turn it on.

    [:octicons-arrow-right-24: Registration](api/registration.md)

-   :material-email-check:{ .lg .middle } __OTP__

    ---

    Ask for a new short code when the last one expired.

    [:octicons-arrow-right-24: OTP](api/otp.md)

-   :material-shield-check:{ .lg .middle } __Activation__

    ---

    Turn a new account on with the code from the email.

    [:octicons-arrow-right-24: Activation](api/activation.md)

-   :material-login:{ .lg .middle } __Login__

    ---

    Sign in with email and a password, or with a short code.

    [:octicons-arrow-right-24: Login](api/login.md)

-   :material-google:{ .lg .middle } __Google login__

    ---

    Sign in with Google. We create the account if you do not have one yet.

    [:octicons-arrow-right-24: Google login](api/google-login.md)

-   :material-account:{ .lg .middle } __Profile__

    ---

    Read or update the profile for the person who is signed in.

    [:octicons-arrow-right-24: Profile](api/profile.md)

-   :material-badge-account:{ .lg .middle } __Staff check__

    ---

    Check whether the signed-in person is a staff member.

    [:octicons-arrow-right-24: Staff check](api/is-staff.md)

-   :material-account-key:{ .lg .middle } __Staff users__

    ---

    An admin adds a staff user and ticks the roles they should have.

    [:octicons-arrow-right-24: Staff users](api/staff-users.md)

-   :material-account-group:{ .lg .middle } __Customers__

    ---

    Read customers and the shipping addresses saved on their orders.

    [:octicons-arrow-right-24: Customers](api/customers.md)

</div>

## Catalog

<div class="grid cards" markdown>

-   :material-post:{ .lg .middle } __Blogs__

    ---

    Read posts without signing in. Staff publish them. Anyone signed in can comment.

    [:octicons-arrow-right-24: Blogs](api/blogs.md)

-   :material-package-variant:{ .lg .middle } __Products__

    ---

    Browse brands, products, and reviews. Each product has a weight in grams, and it starts at 1.

    [:octicons-arrow-right-24: Products](api/products.md)

</div>

## Commerce

<div class="grid cards" markdown>

-   :material-cart:{ .lg .middle } __Cart__

    ---

    Read and replace the cart for the person who is signed in.

    [:octicons-arrow-right-24: Cart](api/cart.md)

-   :material-receipt-text:{ .lg .middle } __Orders__

    ---

    Place an order, then read its items, payment, refunds, and parcel. Staff confirm each item before it ships. An unavailable item stays on the order and drops out of the total, or staff replace it.

    [:octicons-arrow-right-24: Orders](api/orders.md)

-   :material-truck-delivery:{ .lg .middle } __Shipping rates__

    ---

    An admin sets each country's fee for one unit of weight. Checkout charges that fee, or more when the basket is heavier.

    [:octicons-arrow-right-24: Shipping rates](api/shipping-rates.md)

-   :material-warehouse:{ .lg .middle } __Warehouses__

    ---

    Staff can read where orders are received. A manager or admin can change that address.

    [:octicons-arrow-right-24: Warehouses](api/warehouses.md)

-   :material-credit-card:{ .lg .middle } __Payments__

    ---

    Start a payment for an order. Staff record refunds. Payments are created and read.

    [:octicons-arrow-right-24: Payments](api/payments.md)

-   :material-truck:{ .lg .middle } __Shipments__

    ---

    Read where a parcel is. A dispatched or delivered step also updates the order.

    [:octicons-arrow-right-24: Shipments](api/shipments.md)

-   :material-text-box-search:{ .lg .middle } __Staff changes__

    ---

    See who changed an order, a payment, a price, or a refund.

    [:octicons-arrow-right-24: Staff changes](api/audit.md)

</div>

## Base URLs

| Area | URL |
| --- | --- |
| Users | `https://api.endovillehealth.com/api/users/` |
| Blogs | `https://api.endovillehealth.com/api/blogs/` |
| Products | `https://api.endovillehealth.com/api/products/` |
| Orders | `https://api.endovillehealth.com/api/orders/` |

When a route needs you to be signed in, send the access token like this:

```
Authorization: Bearer <access_token>
```

## Responses

Every response is JSON. If a field is wrong, the error uses that field's name. If you are not allowed to do something, or the record is missing, the error is in `detail`.

| Status | What it means |
| --- | --- |
| `200 OK` | The call worked |
| `201 Created` | Something new was saved |
| `400 Bad Request` | A field in the body is missing or invalid |
| `401 Unauthorized` | Sign in, or send a valid access token |
| `403 Forbidden` | You are signed in, but you cannot do this |
| `404 Not Found` | That record is not there |
