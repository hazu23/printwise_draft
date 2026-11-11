# PrintWise To-Do List

This checklist uses simple descriptions so it is easy to follow while building the system.

## Completed

- [x] Customer registration, login, logout, and session protection
- [x] Customer, staff, and admin roles with protected pages
- [x] Customer printshop directory and printshop details modal
- [x] Customer print request form with multiple file uploads
- [x] Customer request tracking, cancellation, prices, and payment status
- [x] Staff/admin request inbox and staff-created requests
- [x] Online QR payment and receipt upload
- [x] Staff/admin receipt inbox with an enlarged receipt modal
- [x] Request and payment reference numbers
- [x] Customer and printshop-worker notifications
- [x] Staff account management for admins
- [x] Service and product management for admins
- [x] Admin controls for adding, enabling, and disabling service choices
- [x] Permanent deletion for unused services and their saved options
- [x] Printshop opening, closing, always-open, and temporarily-closed status
- [x] Search, date filters, and pagination for requests and receipts
- [x] Customer, staff, and admin profile pages
- [x] CSRF protection and custom error pages
- [x] Prevent repeated payment uploads after a receipt is submitted

## Recommended Next Tasks

- [ ] Add Flask-Migrate/Alembic so database changes are saved as migration files
- [ ] Add automated tests for login, permissions, requests, payments, and notifications
- [ ] Add a required password-change flow for newly created staff accounts
- [ ] Let admins reset a staff member's password safely
- [ ] Add notification preferences, such as turning certain alerts on or off
- [ ] Let staff approve or reject a submitted payment receipt with a recorded reason
- [ ] Add daily or weekly business schedules instead of one schedule for every day
- [ ] Add holidays and special closing dates for printshops
- [ ] Add request history showing who changed a status, price, or payment state
- [x] Add secure file cleanup rules for cancelled or old requests
- [x] Add a shared dashboard for staff and admin accounts
- [ ] Prepare production deployment settings, HTTPS, backups, and environment secrets
- [ ] Review accessibility on mobile, keyboard navigation, and screen readers

## Before Deployment

- [ ] Use a production WSGI server instead of Flask's development server
- [ ] Set `APP_ENV=production` and a strong `SECRET_KEY`
- [ ] Use a production MySQL user with limited permissions
- [ ] Enable HTTPS so secure session cookies work
- [ ] Back up the database and uploaded files automatically
- [ ] Test the system using separate customer, staff, and admin accounts
