import os
import sys
import django

sys.path.insert(0, r"d:\DATN\code\enterprise_approval_system")
sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_core.config.settings")
django.setup()

from django.db import connection

with connection.cursor() as cur:
    # 1. Map old dept id -> new dept id
    cur.execute("""
        SELECT old_d.id, new_d.id, new_d.code
        FROM eas.department old_d
        JOIN eas.departments new_d ON (
            new_d.code = old_d.code OR
            new_d.code = 'DEPT_' || old_d.code OR
            (old_d.code = 'TECH' AND new_d.code = 'DEPT_IT') OR
            (old_d.code = 'BIZ' AND new_d.code = 'DEPT_SALES') OR
            (old_d.code = 'MKT' AND new_d.code = 'DEPT_SALES') OR
            (old_d.code = 'LEGAL' AND new_d.code = 'DEPT_HR')
        );
    """)
    dept_map = {str(row[0]): str(row[1]) for row in cur.fetchall()}
    print("Mapped depts count:", len(dept_map))

    # 2. Get role ids
    cur.execute("SELECT id, code FROM eas.roles;")
    role_map = {row[1]: str(row[0]) for row in cur.fetchall()}
    default_role_id = role_map.get("EMPLOYEE")

    # 3. Read app_users and insert into eas.users ON CONFLICT DO UPDATE
    cur.execute("""
        SELECT id, username, display_name, email, department_id, is_active
        FROM eas.app_user;
    """)
    app_users = cur.fetchall()
    print("Found app_users:", len(app_users))
    synced = 0
    for u in app_users:
        u_id, username, display_name, email, old_dept_id, is_active = u
        new_dept_id = dept_map.get(str(old_dept_id)) or "22222222-2222-4222-8222-222222222201"
        code = f"EMP_{username.upper().replace('.', '_')}"
        
        # Decide role
        if "admin" in username or "admin" in email:
            u_role = role_map.get("ADMIN", default_role_id)
            title = "Quản trị viên"
        elif any(k in username for k in ["hung.nguyen", "ngoc.tran", "khoa.dang", "hoang.vu", "lan.ngo", "thanh.do"]):
            u_role = role_map.get("MANAGER", default_role_id)
            title = "Trưởng phòng / Quản lý"
        elif "hr" in username or "hr" in email:
            u_role = role_map.get("HR_SPECIALIST", default_role_id)
            title = "Chuyên viên Nhân sự"
        elif "it" in username or "tech" in username:
            u_role = role_map.get("IT_SPECIALIST", default_role_id)
            title = "Kỹ sư CNTT"
        elif "fin" in username or "ketoan" in username:
            u_role = role_map.get("ACCOUNTANT", default_role_id)
            title = "Chuyên viên Kế toán"
        else:
            u_role = default_role_id
            title = "Nhân viên chuyên trách"

        cur.execute("""
            INSERT INTO eas.users (id, employee_code, full_name, email, job_title, role_id, department_id, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                email = EXCLUDED.email,
                job_title = COALESCE(eas.users.job_title, EXCLUDED.job_title),
                role_id = COALESCE(eas.users.role_id, EXCLUDED.role_id),
                department_id = COALESCE(eas.users.department_id, EXCLUDED.department_id);
        """, [u_id, code, display_name or username, email, title, u_role, new_dept_id, is_active])
        synced += 1
    print("Synced users successfully:", synced)
