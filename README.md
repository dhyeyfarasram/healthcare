# Hospital Management System (Odoo)

An Odoo application for managing patient records, doctor departments, appointments, prescriptions, follow-ups, and visit-related payments. The module extends Odoo's existing contacts, users, and accounting models and includes a patient-facing portal for appointment workflows.

> **Repository:** [dhyeyfarasram/healthcare](https://github.com/dhyeyfarasram/healthcare)  
> **Odoo module name:** Patients  
> **Module version:** 1.0  
> **Category:** Healthcare

## Overview

This project provides a centralized workflow for patient and appointment management inside Odoo. Staff can maintain patient medical information, assign doctors to departments, manage patient visits and prescriptions, and track follow-up appointments. Portal users can view their appointments and submit new appointment requests.

## Features

### Patient records
- Extends Odoo Contacts (`res.partner`) with patient-specific information.
- Stores blood group, allergies, chronic conditions, current medications, and additional medical notes.
- Displays visit and payment counts and provides actions to open related records.

### Doctor and department management
- Adds a doctor designation and department assignment to Odoo users.
- Supports departments with descriptions and an active/inactive flag.
- Displays the doctors assigned to each department and a doctor count.

### Appointment and visit management
- Records the patient, doctor, department, date, time, notes, and visit status.
- Provides 30-minute appointment slots from 08:00 to 18:00.
- Prevents appointments from being scheduled for past dates.
- Checks for conflicting doctor appointments.
- Tracks visit states: Draft, Pending Payment, Scheduled, Completed, and Cancelled.
- Shows a summary of the patient's previous visit, including notes and prescriptions.
- Uses Odoo chatter tracking for selected visit fields.

### Prescriptions
- Adds prescription lines to a patient visit.
- Records the medicine, dosage, and instructions.
- Validates that dosage is positive and does not exceed the configured 10,000 mg upper limit.
- Prevents the same medicine from being added more than once to a visit.

### Follow-ups
- Links follow-up records to a patient visit.
- Tracks the follow-up date, notes, and status (Pending, Done, or Cancelled).
- Makes the related patient and doctor available on the follow-up record.

### Payments
- Extends Odoo `account.payment` with a link to the patient visit.
- Provides a patient-level action and count for related payments.
- Includes a portal token-payment confirmation workflow that marks a visit as paid and records a payment reference.

### Patient portal
Authenticated portal users can:
- View their appointment list with pagination.
- Open a new appointment form.
- Filter available doctors by department.
- Select a doctor, date, and 30-minute time slot.
- Submit notes and optionally attach a PDF, JPG, or PNG report.
- View the payment page and confirm the appointment token payment.
- Cancel an eligible appointment.

### Security and reporting
- Includes security group, record-rule, and model-access configuration files.
- Includes a patient visit report definition.
- Loads portal templates, patient and department views, menus, medical-history views, and scheduled actions through the module manifest.

## Technology stack

- **ERP framework:** Odoo
- **Programming language:** Python
- **UI and templates:** XML / QWeb
- **Data layer:** Odoo ORM
- **Business modules used:** `base`, `account`, `portal`, `mail`

## Repository structure

```text
healthcare/
├── controllers/
│   ├── __init__.py
│   └── portal.py
├── models/
│   ├── __init__.py
│   ├── patient_visit.py
│   ├── patient_prescription_line.py
│   ├── res_partner.py
│   ├── res_users.py
│   ├── account_payment.py
│   ├── follow_up.py
│   └── doctor_department.py
├── report/
│   └── patient_visit_report.xml
├── security/
│   ├── res.groups.xml
│   ├── ir.rules.xml
│   └── ir.model.access.csv
├── views/
│   ├── portal_template.xml
│   ├── doctor_department.xml
│   ├── patient_views.xml
│   ├── patient_menu.xml
│   ├── cron.xml
│   └── medical_history.xml
├── __init__.py
├── __manifest__.py
└── README.md
```

## Requirements

- An installed Odoo instance.
- The Odoo modules listed in the manifest:
  - `base`
  - `account`
  - `portal`
  - `mail`
- Access to the Odoo server's custom/addons directory.

**Odoo version:** The repository manifest does not specify a target Odoo version. Use the version supported by your Odoo environment and verify compatibility before deployment.

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/dhyeyfarasram/healthcare.git
   ```

2. Place the `healthcare` directory in a directory included in your Odoo `addons_path`.

3. Ensure the Python package dependencies for your Odoo installation are installed and that the Odoo service account can read the module files.

4. Restart the Odoo service.

5. Log in to Odoo with an administrator account.

6. Enable **Developer Mode**.

7. Open **Apps**, refresh the Apps List, search for **Patients**, and install the module.

If you manage Odoo from the command line, you can update the Apps List and install the module using your Odoo executable and configuration file. Adapt the database name, config path, and executable path to your environment:

```bash
./odoo-bin -c /path/to/odoo.conf -d your_database -u base --stop-after-init
./odoo-bin -c /path/to/odoo.conf -d your_database -i healthcare --stop-after-init
```

> The technical module name used with `-i` must match the add-on directory name. If you rename the directory, use the new technical name.

## Initial configuration and usage

After installation, an administrator should:

1. Review the healthcare security groups and access rights.
2. Create doctor departments.
3. Create or update Odoo user accounts for doctors, assign their departments, and enable the doctor designation.
4. Create patient contacts and complete their medical information.
5. Configure an outgoing email server if appointment emails or reminders are required.
6. Review accounting configuration before using visit-related payment workflows.
7. Grant portal access to the appropriate patient users.

Typical workflow:

1. A patient signs in to the portal and opens **My Appointments**.
2. The patient chooses a department (if applicable), doctor, date, and available time.
3. The patient submits the request and is directed to the token-payment page.
4. After payment confirmation, staff can manage the visit through its lifecycle.
5. Staff can add prescription lines and schedule follow-ups as needed.

## Important implementation notes

- Appointment slots are represented in 30-minute increments between 08:00 and 18:00.
- The visit model validates past dates and checks overlapping doctor appointments for active visit states.
- The portal controller accepts PDF, JPG, and PNG report uploads.
- The portal payment confirmation code sets the visit's `is_paid` flag and creates a `TOKEN-<visit id>` reference. This code path should not be treated as a verified payment-gateway integration. Connect and validate a real payment provider before using it to collect money.
- Configure and test outgoing mail settings before relying on automated email notifications.
- Review access rules and portal routes carefully before production deployment, especially any use of elevated permissions (`sudo()`).

## Development

To contribute or customize the module:

1. Create a feature branch.
2. Make changes in the relevant model, controller, view, report, or security file.
3. Restart Odoo and upgrade the module in a development database.
4. Test the affected staff and portal workflows with users from each relevant security group.
5. Submit a pull request with a clear description and testing notes.

## Testing checklist

Before deploying, verify at least the following:

- Patient contacts can be created and their medical details saved.
- Doctors can be assigned to departments.
- Past appointment dates are rejected.
- Conflicting appointments for the same doctor are rejected.
- Visit state transitions behave as expected.
- Duplicate medicines and invalid dosage values are rejected.
- Follow-ups are linked to the correct visit, patient, and doctor.
- Portal users can access only their own appointment records.
- Invalid file types are rejected.
- Payment status is updated only through an appropriately secured and verified payment process.
- Email notifications and scheduled actions work with the configured mail server.

## Security and privacy

This application may store sensitive patient and medical information. Before using it with real patient data:

- Review all model access rights, record rules, portal routes, and elevated-permission operations.
- Apply least-privilege access for staff and portal users.
- Use HTTPS and secure Odoo/database backups.
- Avoid committing credentials, patient data, or production configuration to source control.
- Validate payment status with a trusted payment provider rather than relying on a client-accessible confirmation route.
- Ensure deployment and data handling comply with applicable privacy and healthcare regulations.

## Contributing

Contributions, bug reports, and feature suggestions are welcome. Please open an issue to discuss significant changes before submitting a pull request.

## License

No license is declared in the repository manifest or the repository files reviewed. Add a `LICENSE` file and update this section before distributing or reusing the project.

## Author

**Dhyey**

GitHub: [@dhyeyfarasram](https://github.com/dhyeyfarasram)
