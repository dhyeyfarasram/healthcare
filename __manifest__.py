{
    'name': 'Patients',
    'version': '1.0',
    'category': 'Healthcare',
    'summary': 'Manage patient information and appointments',
    'description': """
        This module allows you to manage patient information, including personal details, medical history, and appointments.
    """,
    'author': 'Dhyey',
    'depends': ['base','account','portal','mail'],
    'data': [
        'security/res.groups.xml',
        'security/ir.rules.xml',
        'security/ir.model.access.csv',
        'report/patient_visit_report.xml',
        'views/portal_template.xml',
        'views/doctor_department.xml',
        'views/patient_views.xml',
        'views/patient_menu.xml',
        'views/cron.xml',
        'views/medical_history.xml',
    ],
    "installable": True,
    "application": True,
}
