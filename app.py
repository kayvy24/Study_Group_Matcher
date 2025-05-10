# Merged app.py with full features + privacy
# Includes: /manage, /update, /delete, /edit_group, /view_group, /group_details
# Auto-generates group password and sends it via email
# Protects group details behind login (email + password)

from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail, Message
import csv, os, secrets

app = Flask(__name__)
app.secret_key = 'sdsu-group-secret'

SUBMISSIONS_FILE = 'submissions.csv'
GROUPS_FILE = 'groups.csv'

# Email config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'sdsustudygroupdemo@gmail.com'
app.config['MAIL_PASSWORD'] = 'rbqkooxyqeslbfhc'
app.config['MAIL_DEFAULT_SENDER'] = 'sdsustudygroupdemo@gmail.com'

mail = Mail(app)

# ---- Main group creation + matching route ----
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
        preferences = ', '.join(request.form.getlist('preferences'))
        group_sizes = request.form.getlist('group_size')

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
                    grouped_names.update(m.strip().split(' (')[0].lower() for m in members)

        potential_group = [user_added]
        with open(SUBMISSIONS_FILE, 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                if len(row) < 7:
                    continue
                existing_name, existing_email, existing_course, existing_availability, existing_preferences, existing_group_size, _ = row
                if existing_name.lower() in grouped_names or existing_name == name:
                    continue
                if existing_course == course:
                    existing_times = set(t.strip() for t in existing_availability.lower().split(','))
                    new_times = set(t.strip() for t in availability.lower().split(','))
                    existing_styles = set(s.strip() for s in existing_preferences.lower().split(','))
    new_styles = set(s.strip() for s in preferences.lower().split(','))
    style_overlap = existing_styles & new_styles

    group_size_match = existing_group_size.strip() in group_sizes or not group_sizes

    if existing_times & new_times and style_overlap and group_size_match:
        potential_group.append({
            'name': existing_name,
            'email': existing_email,
            'course': existing_course,
            'availability': existing_availability,
            'preferences': existing_preferences,
            'group_size': existing_group_size
        })

    if str(len(potential_group)) in group_sizes:
        break

        if len(potential_group) == int(group_size):
            group_id = str(sum(1 for _ in open(GROUPS_FILE)) if os.path.exists(GROUPS_FILE) else 1)
            members_str = '|'.join([f"{p['name']} ({p['email']})" for p in potential_group])
            password = secrets.token_urlsafe(6)

            with open(GROUPS_FILE, 'a', newline='') as gfile:
                fieldnames = ['group_id', 'class', 'availability', 'members', 'group_size', 'group_password']
                writer = csv.DictWriter(gfile, fieldnames=fieldnames)
                if gfile.tell() == 0:
                    writer.writeheader()
                writer.writerow({
                    'group_id': group_id,
                    'class': course,
                    'availability': availability,
                    'members': members_str,
                    'group_size': group_size,
                    'group_password': password
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

🔐 Group Password: {password}
Use it to view your group at: {url_for('view_group', group_id=group_id, _external=True)}

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
                    'availability': row['availability']
                })

    return render_template('index.html', submitted=submitted, just_grouped=just_grouped, user=user_added, groups=group_list)

@app.route('/view_group/<group_id>', methods=['GET', 'POST'])
def view_group(group_id):
    error = ''
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password'].strip()

        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row['group_id'] == group_id and row['group_password'] == password:
                        if any(email in m.lower() for m in row['members'].split('|')):
                            session['authorized_group'] = group_id
                            return redirect(url_for('group_details', group_id=group_id))
        error = 'Invalid email or password.'

    return render_template('group_login.html', group_id=group_id, error=error)

@app.route('/group_details/<group_id>')
def group_details(group_id):
    if session.get('authorized_group') != group_id:
        return redirect(url_for('view_group', group_id=group_id))

    group_info = None
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['group_id'] == group_id:
                    group_info = row
                    group_info['members'] = row['members'].split('|')
                    break

    return render_template('group_details.html', group=group_info)

# /manage, /update, /delete, /edit_group, /update_group, /delete_group routes now merged in below

# (Those routes would follow here, after the password features.)

@app.route('/manage', methods=['GET', 'POST'])
def manage():
    user_data = None
    message = ''
    status = request.args.get('status', '')

    if request.method == 'POST':
        email = request.form['email'].strip().lower()

        if os.path.exists(SUBMISSIONS_FILE):
            with open(SUBMISSIONS_FILE, 'r') as file:
                reader = csv.reader(file)
                for row in reader:
                    if len(row) >= 7 and row[1].strip().lower() == email:
                        user_data = {
                            'name': row[0],
                            'email': row[1],
                            'course': row[2],
                            'availability': row[3],
                            'preferences': row[4],
                            'group_size': row[5]
                        }

        if not user_data:
            message = "No submission found for that email."

    return render_template('manage.html', user=user_data, message=message, status=status)

@app.route('/update', methods=['POST'])
def update():
    email = request.form['email'].strip().lower()
    new_rows = []
    updated_row = None

    if os.path.exists(SUBMISSIONS_FILE):
        with open(SUBMISSIONS_FILE, 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                if len(row) >= 7 and row[1].strip().lower() == email:
                    updated_row = [
                        request.form['name'],
                        email,
                        request.form['course'],
                        request.form['availability'],
                        request.form['preferences'],
                        request.form['group_size'],
                        'yes'
                    ]
                    row = updated_row
                new_rows.append(row)

        with open(SUBMISSIONS_FILE, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(new_rows)

        try:
            if updated_row:
                msg = Message(
                    subject="✏️ Your SDSU Study Group Info Was Updated",
                    recipients=[email]
                )
                msg.body = f"""Hi,

Your submission has been updated:

• Course: {updated_row[2].upper()}
• Availability: {updated_row[3]}
• Study Style: {updated_row[4]}
• Group Size: {updated_row[5]}

You can return to update or delete at any time.

— SDSU Study Group Matcher
"""
                mail.send(msg)
        except Exception as e:
            print("❌ Update email error:", str(e))

    return redirect(url_for('manage', status='updated'))

@app.route('/delete', methods=['POST'])
def delete():
    email = request.form['email'].strip().lower()
    new_rows = []
    deleted_name = None

    if os.path.exists(SUBMISSIONS_FILE):
        with open(SUBMISSIONS_FILE, 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                if len(row) >= 2 and row[1].strip().lower() != email:
                    new_rows.append(row)
                elif row[1].strip().lower() == email:
                    deleted_name = row[0]

        with open(SUBMISSIONS_FILE, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(new_rows)

        try:
            if deleted_name:
                msg = Message(
                    subject="❌ Your Study Group Submission Was Removed",
                    recipients=[email]
                )
                msg.body = f"""Hi {deleted_name},

Your SDSU Study Group submission has been successfully removed.

You're always welcome to re-submit if you're still looking for a group.

— SDSU Study Group Matcher
"""
                mail.send(msg)
        except Exception as e:
            print("❌ Delete email error:", str(e))

    return redirect(url_for('manage', status='deleted'))

@app.route('/edit_group', methods=['GET', 'POST'])
def edit_group():
    group_info = None
    email = ""
    message = ""
    status = request.args.get('status', '')

    if request.method == 'POST':
        email = request.form['email'].strip().lower()

        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, 'r') as gfile:
                reader = csv.DictReader(gfile)
                for row in reader:
                    members = [m.strip() for m in row['members'].split('|')]
                    if any(email in m.lower() for m in members):
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

    return render_template('edit_group.html', group=group_info, email=email, message=message, status=status)

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
            fieldnames = ['group_id', 'class', 'availability', 'members', 'group_size', 'group_password']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)

    return redirect(url_for('edit_group', status='updated'))

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
            fieldnames = ['group_id', 'class', 'availability', 'members', 'group_size', 'group_password']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)

    return redirect(url_for('edit_group', status='deleted'))

if __name__ == '__main__':
    app.run(debug=True)
