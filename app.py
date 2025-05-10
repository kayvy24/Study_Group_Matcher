from flask import Flask, render_template, request, redirect, url_for
from flask_mail import Mail, Message
import csv, os

app = Flask(__name__)
app.secret_key = 'sdsu-group-secret'

SUBMISSIONS_FILE = 'submissions.csv'
GROUPS_FILE = 'groups.csv'

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'sdsustudygroupdemo@gmail.com'
app.config['MAIL_PASSWORD'] = 'rbqkooxyqeslbfhc'
app.config['MAIL_DEFAULT_SENDER'] = 'sdsustudygroupdemo@gmail.com'

mail = Mail(app)

@app.route('/', methods=['GET', 'POST'])
def index():
    submitted = False
    just_grouped = False
    user_added = {}
    group_list = []

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].strip().lower()
        course = request.form['course'].lower().strip()
        availability_list = request.form.getlist('availability')
        availability = ', '.join([a.lower().strip() for a in availability_list])
        preferences = request.form['preferences']
        group_size = request.form.get('group_size', '').strip()

        submitted = True

        user_added = {
            'name': name,
            'email': email,
            'course': course,
            'availability': availability,
            'preferences': preferences,
            'group_size': group_size
        }

        with open(SUBMISSIONS_FILE, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([name, email, course, availability, preferences, group_size, 'yes'])

        grouped_names = set()
        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, 'r') as gfile:
                reader = csv.DictReader(gfile)
                for row in reader:
                    members = row['members'].split('|')
                    grouped_names.update(members)

        potential_group = [user_added]
        with open(SUBMISSIONS_FILE, 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                if len(row) < 7:
                    continue
                existing_name, existing_email, existing_course, existing_availability, existing_preferences, existing_group_size, _ = row
                if existing_name in grouped_names or existing_name == name:
                    continue
                if existing_course == course:
                    existing_times = set(t.strip() for t in existing_availability.lower().split(','))
                    new_times = set(t.strip() for t in availability.lower().split(','))
                    if existing_times & new_times:
                        potential_group.append({
                            'name': existing_name,
                            'email': existing_email,
                            'course': existing_course,
                            'availability': existing_availability,
                            'preferences': existing_preferences,
                            'group_size': existing_group_size
                        })
                if len(potential_group) == int(group_size):
                    break

        existing_group_joined = False
        updated_groups = []

        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, 'r') as gfile:
                reader = csv.DictReader(gfile)
                for row in reader:
                    if row['class'] == course:
                        group_times = set(t.strip() for t in row['availability'].lower().split(','))
                        new_times = set(t.strip() for t in availability.lower().split(','))
                        if group_times & new_times:
                            members = row['members'].split('|')
                            if len(members) < int(row['group_size']):
                                members.append(name)
                                updated_groups.append({
                                    'group_id': row['group_id'],
                                    'class': course,
                                    'availability': row['availability'],
                                    'members': '|'.join(members),
                                    'group_size': row['group_size']
                                })
                                existing_group_joined = True
                                just_grouped = True

                                try:
                                    msg = Message(
                                        subject=f"🎓 You've Joined a {course.upper()} Study Group!",
                                        recipients=[email]
                                    )
                                    msg.body = f"""Hi {name},

You've been added to an existing study group for {course.upper()}.

📅 Time: {row['availability']}
📍 Location: Love Library, 2nd Floor

Group members:
{chr(10).join('• ' + m for m in members)}

— SDSU Study Group Matcher
"""
                                    mail.send(msg)
                                except Exception as e:
                                    print("❌ Email error on join:", str(e))
                                continue
                    updated_groups.append(row)

            if existing_group_joined:
                with open(GROUPS_FILE, 'w', newline='') as gfile:
                    fieldnames = ['group_id', 'class', 'availability', 'members', 'group_size']
                    writer = csv.DictWriter(gfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(updated_groups)

        if not existing_group_joined and len(potential_group) == int(group_size):
            group_id = str(sum(1 for _ in open(GROUPS_FILE)) if os.path.exists(GROUPS_FILE) else 1)
            members_str = '|'.join([p['name'] for p in potential_group])
            with open(GROUPS_FILE, 'a', newline='') as gfile:
                fieldnames = ['group_id', 'class', 'availability', 'members', 'group_size']
                writer = csv.DictWriter(gfile, fieldnames=fieldnames)
                if gfile.tell() == 0:
                    writer.writeheader()
                writer.writerow({
                    'group_id': group_id,
                    'class': course,
                    'availability': availability,
                    'members': members_str,
                    'group_size': group_size
                })
            just_grouped = True

            try:
                emails = [p['email'] for p in potential_group]
                names = [f"• {p['name']}" for p in potential_group]
                location = "Love Library, 2nd Floor"

                msg = Message(
                    subject=f"🎓 You're Matched for {course.upper()}!",
                    recipients=emails
                )
                msg.body = f"""Hi,

You've been matched into a study group for {course.upper()} with:

{chr(10).join(names)}

📅 Time: {availability}
📍 Suggested Location: {location}

Good luck and happy studying!

— SDSU Study Group Matcher
"""
                mail.send(msg)
            except Exception as e:
                print("❌ Match email error:", str(e))

    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, 'r') as gfile:
            reader = csv.DictReader(gfile)
            for row in reader:
                group_list.append({
                    'group_id': row['group_id'],
                    'course': row['class'],
                    'availability': row['availability'],
                    'members': row['members'].split('|')
                })

    return render_template('index.html',
        submitted=submitted,
        just_grouped=just_grouped,
        user=user_added,
        groups=group_list
    )

@app.route('/edit_group', methods=['GET', 'POST'])
def edit_group():
    group_info = None
    email = ""
    message = ""

    if request.method == 'POST':
        email = request.form['email'].strip().lower()

        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, 'r') as gfile:
                reader = csv.DictReader(gfile)
                for row in reader:
                    members = [m.strip().lower() for m in row['members'].split('|')]
                    if email in members:
                        group_info = {
                            'group_id': row['group_id'],
                            'course': row['class'],
                            'availability': row['availability'],
                            'members': members,
                            'group_size': row.get('group_size', 'N/A')
                        }
                        break
                if not group_info:
                    message = "No group found for that email."

    return render_template('edit_group.html', group=group_info, email=email, message=message)

@app.route('/update_group', methods=['POST'])
def update_group():
    group_id = request.form['group_id']
    new_availability = request.form['availability'].strip().lower()
    new_group_size = request.form['group_size'].strip()
    updated_rows = []

    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['group_id'] == group_id:
                    row['availability'] = new_availability
                    row['group_size'] = new_group_size
                updated_rows.append(row)

        with open(GROUPS_FILE, 'w', newline='') as file:
            fieldnames = ['group_id', 'class', 'availability', 'members', 'group_size']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)

    return redirect(url_for('edit_group'))

@app.route('/delete_group', methods=['POST'])
def delete_group():
    group_id = request.form['group_id']
    updated_rows = []

    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['group_id'] != group_id:
                    updated_rows.append(row)

        with open(GROUPS_FILE, 'w', newline='') as file:
            fieldnames = ['group_id', 'class', 'availability', 'members', 'group_size']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)

    return redirect(url_for('edit_group'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
