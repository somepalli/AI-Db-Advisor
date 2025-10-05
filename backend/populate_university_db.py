#!/usr/bin/env python3
"""
Script to populate UniversityDB with 10000-15000 rows per table
"""

import psycopg
from psycopg.rows import dict_row
import random
from datetime import datetime, timedelta, date

DSN = "postgresql://postgres:postgres@localhost:5432/UniversityDB"

# Sample data
first_names = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emma', 'James', 'Emily', 'Robert', 'Olivia',
               'William', 'Sophia', 'Joseph', 'Isabella', 'Charles', 'Mia', 'Thomas', 'Charlotte', 'Daniel', 'Amelia']

last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
              'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin']

department_names = ['Computer Science', 'Mathematics', 'Physics', 'Chemistry', 'Biology', 'English', 'History',
                    'Economics', 'Psychology', 'Engineering']

course_names = ['Introduction to Programming', 'Data Structures', 'Algorithms', 'Database Systems', 'Operating Systems',
                'Calculus I', 'Calculus II', 'Linear Algebra', 'Differential Equations', 'Statistics',
                'Classical Mechanics', 'Quantum Physics', 'Thermodynamics', 'Electromagnetism',
                'Organic Chemistry', 'Inorganic Chemistry', 'Analytical Chemistry', 'Physical Chemistry',
                'Cell Biology', 'Genetics', 'Ecology', 'Microbiology',
                'English Literature', 'Creative Writing', 'World History', 'American History',
                'Microeconomics', 'Macroeconomics', 'Cognitive Psychology', 'Social Psychology']

book_titles = ['Introduction to Algorithms', 'Design Patterns', 'Clean Code', 'The Pragmatic Programmer',
               'Head First Java', 'You Do not Know JS', 'Eloquent JavaScript', 'Python Crash Course',
               'Calculus Early Transcendentals', 'Linear Algebra and Its Applications',
               'University Physics', 'Principles of Quantum Mechanics', 'Chemistry The Central Science',
               'Campbell Biology', 'Molecular Biology of the Cell', 'The Norton Anthology of English Literature',
               'A History of Western Society', 'Principles of Economics', 'Psychology by David Myers']

book_authors = ['Thomas Cormen', 'Gang of Four', 'Robert Martin', 'Andrew Hunt',
                'Kathy Sierra', 'Kyle Simpson', 'Marijn Haverbeke', 'Eric Matthes',
                'James Stewart', 'David Lay', 'Hugh Young', 'David Griffiths',
                'Theodore Brown', 'Jane Reece', 'Bruce Alberts', 'Stephen Greenblatt',
                'John McKay', 'Gregory Mankiw', 'David Myers']

hostel_names = ['North Hall', 'South Hall', 'East Wing', 'West Wing', 'Central Tower',
                'Oak Residence', 'Pine Lodge', 'Maple House', 'Cedar Hall', 'Birch Building']

def populate_departments(conn, num_rows=10):
    """Insert department data"""
    print(f"Inserting departments...")

    with conn.cursor() as cur:
        # Clear existing data
        cur.execute("TRUNCATE TABLE departments CASCADE")

        departments = []
        for i in range(num_rows):
            departments.append((
                i + 1,
                department_names[i % len(department_names)] + (f" {i//len(department_names) + 1}" if i >= len(department_names) else ""),
                f"Prof. {random.choice(first_names)} {random.choice(last_names)}"
            ))

        cur.executemany(
            "INSERT INTO departments (department_id, department_name, hod) VALUES (%s, %s, %s)",
            departments
        )
        conn.commit()

    print(f"  Inserted {num_rows} departments")
    return num_rows

def populate_students(conn, num_departments, num_rows=12000):
    """Insert student data"""
    print(f"Inserting {num_rows} students...")

    with conn.cursor() as cur:
        # Clear existing data
        cur.execute("TRUNCATE TABLE students CASCADE")

        students = []
        for i in range(num_rows):
            dob = date(random.randint(1998, 2005), random.randint(1, 12), random.randint(1, 28))
            first = random.choice(first_names)
            last = random.choice(last_names)

            students.append((
                i + 1,
                first,
                last,
                dob,
                f"{first.lower()}.{last.lower()}{i}@university.edu",
                random.randint(1, num_departments),
                random.randint(2018, 2024)
            ))

            if len(students) >= 1000:
                cur.executemany(
                    """INSERT INTO students
                    (student_id, first_name, last_name, dob, email, department_id, enrollment_year)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    students
                )
                conn.commit()
                students = []
                print(f"  Inserted {i + 1} students...")

        if students:
            cur.executemany(
                """INSERT INTO students
                (student_id, first_name, last_name, dob, email, department_id, enrollment_year)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                students
            )
            conn.commit()

    print(f"  Completed: {num_rows} students")
    return num_rows

def populate_professors(conn, num_departments, num_rows=500):
    """Insert professor data"""
    print(f"Inserting {num_rows} professors...")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE professors CASCADE")

        professors = []
        for i in range(num_rows):
            first = random.choice(first_names)
            last = random.choice(last_names)

            professors.append((
                i + 1,
                f"Prof. {first} {last}",
                random.randint(1, num_departments),
                f"{first.lower()}.{last.lower()}{i}@university.edu"
            ))

            if len(professors) >= 100:
                cur.executemany(
                    "INSERT INTO professors (professor_id, name, department_id, email) VALUES (%s, %s, %s, %s)",
                    professors
                )
                conn.commit()
                professors = []

        if professors:
            cur.executemany(
                "INSERT INTO professors (professor_id, name, department_id, email) VALUES (%s, %s, %s, %s)",
                professors
            )
            conn.commit()

    print(f"  Completed: {num_rows} professors")
    return num_rows

def populate_courses(conn, num_departments, num_rows=150):
    """Insert course data"""
    print(f"Inserting {num_rows} courses...")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE courses CASCADE")

        courses = []
        for i in range(num_rows):
            courses.append((
                i + 1,
                course_names[i % len(course_names)] + (f" - Level {i//len(course_names) + 1}" if i >= len(course_names) else ""),
                random.randint(1, num_departments),
                random.choice([2, 3, 4])
            ))

        cur.executemany(
            "INSERT INTO courses (course_id, course_name, department_id, credits) VALUES (%s, %s, %s, %s)",
            courses
        )
        conn.commit()

    print(f"  Completed: {num_rows} courses")
    return num_rows

def populate_enrollments(conn, num_students, num_courses, num_rows=15000):
    """Insert enrollment data"""
    print(f"Inserting {num_rows} enrollments...")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE enrollments CASCADE")

        semesters = ['Fall 2020', 'Spring 2021', 'Fall 2021', 'Spring 2022', 'Fall 2022', 'Spring 2023', 'Fall 2023', 'Spring 2024']
        grades = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F']

        enrollments = []
        for i in range(num_rows):
            enrollments.append((
                i + 1,
                random.randint(1, num_students),
                random.randint(1, num_courses),
                random.choice(semesters),
                random.choice(grades)
            ))

            if len(enrollments) >= 1000:
                cur.executemany(
                    """INSERT INTO enrollments
                    (enrollment_id, student_id, course_id, semester, grade)
                    VALUES (%s, %s, %s, %s, %s)""",
                    enrollments
                )
                conn.commit()
                enrollments = []
                print(f"  Inserted {i + 1} enrollments...")

        if enrollments:
            cur.executemany(
                """INSERT INTO enrollments
                (enrollment_id, student_id, course_id, semester, grade)
                VALUES (%s, %s, %s, %s, %s)""",
                enrollments
            )
            conn.commit()

    print(f"  Completed: {num_rows} enrollments")

def populate_fees(conn, num_students, num_rows=12000):
    """Insert fee data"""
    print(f"Inserting {num_rows} fees...")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE fees CASCADE")

        statuses = ['Paid', 'Pending', 'Overdue', 'Partial']

        fees = []
        for i in range(num_rows):
            due_date = date.today() - timedelta(days=random.randint(0, 365))
            amount = round(random.uniform(1000, 5000), 2)

            fees.append((
                i + 1,
                random.randint(1, num_students),
                amount,
                due_date,
                random.choice(statuses)
            ))

            if len(fees) >= 1000:
                cur.executemany(
                    "INSERT INTO fees (fee_id, student_id, amount, due_date, status) VALUES (%s, %s, %s, %s, %s)",
                    fees
                )
                conn.commit()
                fees = []
                print(f"  Inserted {i + 1} fees...")

        if fees:
            cur.executemany(
                "INSERT INTO fees (fee_id, student_id, amount, due_date, status) VALUES (%s, %s, %s, %s, %s)",
                fees
            )
            conn.commit()

    print(f"  Completed: {num_rows} fees")

def populate_hostels(conn, num_rows=20):
    """Insert hostel data"""
    print(f"Inserting {num_rows} hostels...")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE hostel CASCADE")

        hostels = []
        for i in range(num_rows):
            hostels.append((
                i + 1,
                hostel_names[i % len(hostel_names)] + (f" {i//len(hostel_names) + 1}" if i >= len(hostel_names) else ""),
                random.randint(100, 500),
                f"Warden {random.choice(first_names)} {random.choice(last_names)}"
            ))

        cur.executemany(
            "INSERT INTO hostel (hostel_id, hostel_name, capacity, warden_name) VALUES (%s, %s, %s, %s)",
            hostels
        )
        conn.commit()

    print(f"  Completed: {num_rows} hostels")
    return num_rows

def populate_hostel_allocation(conn, num_students, num_hostels, num_rows=10000):
    """Insert hostel allocation data"""
    print(f"Inserting {num_rows} hostel allocations...")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE hostelallocation CASCADE")

        allocations = []
        for i in range(num_rows):
            allocation_date = date.today() - timedelta(days=random.randint(0, 1460))

            allocations.append((
                i + 1,
                random.randint(1, num_students),
                random.randint(1, num_hostels),
                str(random.randint(101, 999)),
                allocation_date
            ))

            if len(allocations) >= 1000:
                cur.executemany(
                    """INSERT INTO hostelallocation
                    (allocation_id, student_id, hostel_id, room_no, allocation_date)
                    VALUES (%s, %s, %s, %s, %s)""",
                    allocations
                )
                conn.commit()
                allocations = []
                print(f"  Inserted {i + 1} allocations...")

        if allocations:
            cur.executemany(
                """INSERT INTO hostelallocation
                (allocation_id, student_id, hostel_id, room_no, allocation_date)
                VALUES (%s, %s, %s, %s, %s)""",
                allocations
            )
            conn.commit()

    print(f"  Completed: {num_rows} hostel allocations")

def populate_library_books(conn, num_departments, num_rows=5000):
    """Insert library book data"""
    print(f"Inserting {num_rows} library books...")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE librarybooks CASCADE")

        books = []
        for i in range(num_rows):
            books.append((
                i + 1,
                book_titles[i % len(book_titles)] + (f" - Edition {i//len(book_titles) + 1}" if i >= len(book_titles) else ""),
                book_authors[i % len(book_authors)],
                random.randint(1, num_departments),
                random.randint(1, 10)
            ))

            if len(books) >= 1000:
                cur.executemany(
                    """INSERT INTO librarybooks
                    (book_id, title, author, department_id, available_copies)
                    VALUES (%s, %s, %s, %s, %s)""",
                    books
                )
                conn.commit()
                books = []
                print(f"  Inserted {i + 1} books...")

        if books:
            cur.executemany(
                """INSERT INTO librarybooks
                (book_id, title, author, department_id, available_copies)
                VALUES (%s, %s, %s, %s, %s)""",
                books
            )
            conn.commit()

    print(f"  Completed: {num_rows} library books")
    return num_rows

def populate_book_loans(conn, num_students, num_books, num_rows=14000):
    """Insert book loan data"""
    print(f"Inserting {num_rows} book loans...")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE bookloans CASCADE")

        loans = []
        for i in range(num_rows):
            loan_date = date.today() - timedelta(days=random.randint(0, 365))
            return_date = loan_date + timedelta(days=random.randint(7, 30)) if random.random() > 0.3 else None

            loans.append((
                i + 1,
                random.randint(1, num_students),
                random.randint(1, num_books),
                loan_date,
                return_date
            ))

            if len(loans) >= 1000:
                cur.executemany(
                    "INSERT INTO bookloans (loan_id, student_id, book_id, loan_date, return_date) VALUES (%s, %s, %s, %s, %s)",
                    loans
                )
                conn.commit()
                loans = []
                print(f"  Inserted {i + 1} loans...")

        if loans:
            cur.executemany(
                "INSERT INTO bookloans (loan_id, student_id, book_id, loan_date, return_date) VALUES (%s, %s, %s, %s, %s)",
                loans
            )
            conn.commit()

    print(f"  Completed: {num_rows} book loans")

def show_final_counts(conn):
    """Show final row counts"""
    print("\n" + "="*60)
    print("Final Table Row Counts:")
    print("="*60)

    with conn.cursor() as cur:
        tables = ['departments', 'students', 'professors', 'courses', 'enrollments',
                  'fees', 'hostel', 'hostelallocation', 'librarybooks', 'bookloans']

        for table in tables:
            cur.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cur.fetchone()['count']
            print(f"  {table:20} {count:>10,} rows")

    print("="*60)

def main():
    """Main population function"""
    print("Populating UniversityDB with sample data...")
    print(f"Connecting to: {DSN}\n")

    try:
        with psycopg.connect(DSN, row_factory=dict_row) as conn:
            # Populate in order due to foreign keys
            num_departments = populate_departments(conn, 10)
            num_students = populate_students(conn, num_departments, 12000)
            num_professors = populate_professors(conn, num_departments, 500)
            num_courses = populate_courses(conn, num_departments, 150)
            populate_enrollments(conn, num_students, num_courses, 15000)
            populate_fees(conn, num_students, 12000)
            num_hostels = populate_hostels(conn, 20)
            populate_hostel_allocation(conn, num_students, num_hostels, 10000)
            num_books = populate_library_books(conn, num_departments, 5000)
            populate_book_loans(conn, num_students, num_books, 14000)

            show_final_counts(conn)

            print("\nData population complete!")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
