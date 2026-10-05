import os
from datetime import date
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import mysql.connector
from mysql.connector import Error

# ============================================================
# LIBRARY MANAGEMENT & ANALYTICS SYSTEM
# CBSE CLASS XII INFORMATICS PRACTICES PROJECT
# Python + Streamlit + Pandas + Matplotlib + MySQL
# ============================================================

st.set_page_config(
    page_title="Library Management System",
    page_icon="📚",
    layout="wide"
)

FINE_PER_DAY = 5


# ------------------------- DATABASE --------------------------

def db_config():
    """
    Reads MySQL credentials from Streamlit secrets.
    Falls back to environment variables.
    """
    try:
        secrets = st.secrets
    except Exception:
        secrets = {}

    return {
        "host": secrets.get("MYSQL_HOST", os.getenv("MYSQL_HOST", "localhost")),
        "port": int(secrets.get("MYSQL_PORT", os.getenv("MYSQL_PORT", "3306"))),
        "user": secrets.get("MYSQL_USER", os.getenv("MYSQL_USER", "root")),
        "password": secrets.get("MYSQL_PASSWORD", os.getenv("MYSQL_PASSWORD", "")),
        "database": secrets.get(
            "MYSQL_DATABASE",
            os.getenv("MYSQL_DATABASE", "library_management")
        ),
    }


def get_connection():
    cfg = db_config()

    try:
        connection = mysql.connector.connect(**cfg)

        if connection.is_connected():
            return connection, None

        return None, "Could not establish a MySQL connection."

    except Error as e:
        return None, str(e)


def query_df(sql, params=None):
    """Run SELECT query and return a Pandas DataFrame."""
    connection, error = get_connection()

    if connection is None:
        return pd.DataFrame(), error

    try:
        cursor = connection.cursor()
        cursor.execute(sql, params or ())
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        return pd.DataFrame(rows, columns=columns), None

    except Error as e:
        return pd.DataFrame(), str(e)

    finally:
        connection.close()


def execute_query(sql, params=None):
    """Run INSERT/UPDATE/DELETE query."""
    connection, error = get_connection()

    if connection is None:
        return False, error

    try:
        cursor = connection.cursor()
        cursor.execute(sql, params or ())
        connection.commit()
        return True, None

    except Error as e:
        connection.rollback()
        return False, str(e)

    finally:
        connection.close()


# ------------------------- HELPERS ---------------------------

def get_books():
    return query_df("""
        SELECT
            book_id AS `Book ID`,
            title AS `Title`,
            author AS `Author`,
            category AS `Category`,
            publication_year AS `Publication Year`,
            quantity AS `Quantity`,
            available AS `Available`
        FROM books
        ORDER BY book_id
    """)


def get_members():
    return query_df("""
        SELECT
            m.member_id AS `Member ID`,
            m.name AS `Name`,
            m.class_section AS `Class/Section`,
            m.phone AS `Phone`,
            m.email AS `Email`,
            COALESCE(SUM(
                CASE
                    WHEN t.return_date IS NULL
                         AND CURDATE() > t.due_date
                    THEN DATEDIFF(CURDATE(), t.due_date) * %s
                    WHEN t.return_date IS NOT NULL
                         AND t.return_date > t.due_date
                    THEN DATEDIFF(t.return_date, t.due_date) * %s
                    ELSE 0
                END
            ), 0) AS `Fine (₹)`
        FROM members m
        LEFT JOIN transactions t
            ON m.member_id = t.member_id
        GROUP BY
            m.member_id, m.name, m.class_section, m.phone, m.email
        ORDER BY m.member_id
    """, (FINE_PER_DAY, FINE_PER_DAY))


def get_transactions():
    return query_df("""
        SELECT
            t.transaction_id AS `Transaction ID`,
            b.title AS `Book`,
            m.name AS `Member`,
            t.issue_date AS `Issue Date`,
            t.due_date AS `Due Date`,
            t.return_date AS `Return Date`,
            CASE
                WHEN t.return_date IS NOT NULL
                     AND t.return_date > t.due_date
                THEN DATEDIFF(t.return_date, t.due_date) * %s
                WHEN t.return_date IS NULL
                     AND CURDATE() > t.due_date
                THEN DATEDIFF(CURDATE(), t.due_date) * %s
                ELSE 0
            END AS `Fine (₹)`
        FROM transactions t
        JOIN books b ON t.book_id = b.book_id
        JOIN members m ON t.member_id = m.member_id
        ORDER BY t.transaction_id DESC
    """, (FINE_PER_DAY, FINE_PER_DAY))


def calculate_fine(due_date, return_date=None):
    """Calculate fine at ₹5/day after due date."""
    end_date = return_date if return_date else date.today()

    if end_date > due_date:
        return (end_date - due_date).days * FINE_PER_DAY

    return 0


def show_db_error(error):
    st.error("Database connection/query error.")
    st.code(str(error))


# ------------------------- SIDEBAR ---------------------------

st.sidebar.title("📚 Library System")
st.sidebar.caption("CBSE Class XII IP Project")

page = st.sidebar.radio(
    "Navigation",
    [
        "🏠 Dashboard",
        "📚 Books",
        "👥 Members",
        "🔄 Transactions",
        "📊 Analytics",
        "🗄️ Database"
    ]
)

st.sidebar.divider()
st.sidebar.info(f"Fine rate: ₹{FINE_PER_DAY} per overdue day")


# ============================================================
# DASHBOARD
# ============================================================

if page == "🏠 Dashboard":

    st.title("📚 Library Management & Analytics System")
    st.subheader("Dashboard")

    books, books_error = get_books()
    members, members_error = get_members()
    transactions, transactions_error = get_transactions()

    if books_error:
        show_db_error(books_error)
        st.stop()

    if members_error:
        show_db_error(members_error)
        st.stop()

    if transactions_error:
        show_db_error(transactions_error)
        st.stop()

    total_titles = len(books)
    total_copies = int(books["Quantity"].sum()) if not books.empty else 0
    available_copies = int(books["Available"].sum()) if not books.empty else 0
    issued_copies = total_copies - available_copies
    total_members = len(members)

    overdue = 0
    if not transactions.empty:
        for _, row in transactions.iterrows():
            if pd.isna(row["Return Date"]):
                due = row["Due Date"]
                if hasattr(due, "date"):
                    due = due.date()
                if due < date.today():
                    overdue += 1

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("📚 Book Titles", total_titles)
    c2.metric("📦 Total Copies", total_copies)
    c3.metric("✅ Available", available_copies)
    c4.metric("📤 Issued", issued_copies)
    c5.metric("⚠️ Overdue", overdue)

    st.divider()

    st.subheader("Recent Transactions")

    if transactions.empty:
        st.info("No transactions found.")
    else:
        st.dataframe(
            transactions.head(10),
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# BOOKS
# ============================================================

elif page == "📚 Books":

    st.title("📚 Book Management")

    tab1, tab2, tab3 = st.tabs([
        "➕ Add Book",
        "🔎 Search / View",
        "🗑️ Delete Book"
    ])

    # ---------------- ADD BOOK ----------------

    with tab1:
        st.subheader("Add a New Book")

        with st.form("add_book_form"):
            title = st.text_input("Book Title")
            author = st.text_input("Author")
            category = st.text_input("Category")
            publication_year = st.number_input(
                "Publication Year",
                min_value=0,
                max_value=2100,
                value=2026
            )
            quantity = st.number_input(
                "Quantity",
                min_value=1,
                value=1,
                step=1
            )

            submitted = st.form_submit_button("Add Book")

            if submitted:
                if not title.strip() or not author.strip() or not category.strip():
                    st.warning("Please fill in Title, Author and Category.")
                else:
                    success, error = execute_query(
                        """
                        INSERT INTO books
                        (title, author, category, publication_year, quantity, available)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            title.strip(),
                            author.strip(),
                            category.strip(),
                            publication_year,
                            quantity,
                            quantity
                        )
                    )

                    if success:
                        st.success("Book added successfully!")
                        st.rerun()
                    else:
                        show_db_error(error)

    # ---------------- SEARCH / VIEW ----------------

    with tab2:
        st.subheader("Search Books")

        search = st.text_input(
            "Search by title, author or category",
            placeholder="e.g. Physics"
        )

        books, error = get_books()

        if error:
            show_db_error(error)
        else:
            if search.strip():
                mask = (
                    books["Title"].astype(str).str.contains(
                        search, case=False, na=False
                    )
                    |
                    books["Author"].astype(str).str.contains(
                        search, case=False, na=False
                    )
                    |
                    books["Category"].astype(str).str.contains(
                        search, case=False, na=False
                    )
                )
                books = books[mask]

            st.dataframe(
                books,
                use_container_width=True,
                hide_index=True
            )

    # ---------------- DELETE BOOK ----------------

    with tab3:
        st.subheader("Delete a Book")

        books_raw, error = query_df("""
            SELECT book_id, title
            FROM books
            ORDER BY title
        """)

        if error:
            show_db_error(error)
        elif books_raw.empty:
            st.info("No books available to delete.")
        else:
            book_options = {
                f"{row['title']} (ID: {row['book_id']})": int(row["book_id"])
                for _, row in books_raw.iterrows()
            }

            selected = st.selectbox(
                "Select book",
                list(book_options.keys())
            )

            st.warning(
                "Deleting a book is permanent. A book with transaction history "
                "cannot be deleted because that would break borrowing records."
            )

            if st.button("🗑️ Delete Selected Book", type="secondary"):
                book_id = book_options[selected]

                history, history_error = query_df(
                    """
                    SELECT transaction_id
                    FROM transactions
                    WHERE book_id = %s
                    LIMIT 1
                    """,
                    (book_id,)
                )

                if history_error:
                    show_db_error(history_error)
                elif not history.empty:
                    st.error(
                        "This book has transaction history and cannot be deleted."
                    )
                else:
                    success, delete_error = execute_query(
                        "DELETE FROM books WHERE book_id = %s",
                        (book_id,)
                    )

                    if success:
                        st.success("Book deleted successfully.")
                        st.rerun()
                    else:
                        show_db_error(delete_error)


# ============================================================
# MEMBERS
# ============================================================

elif page == "👥 Members":

    st.title("👥 Member Management")

    tab1, tab2, tab3 = st.tabs([
        "➕ Add Member",
        "👥 View Members",
        "🗑️ Delete Member"
    ])

    # ---------------- ADD MEMBER ----------------

    with tab1:
        st.subheader("Register New Member")

        with st.form("add_member_form"):
            name = st.text_input("Member Name")
            class_section = st.text_input("Class / Section")
            phone = st.text_input("Phone")
            email = st.text_input("Email")

            submitted = st.form_submit_button("Add Member")

            if submitted:
                if not name.strip():
                    st.warning("Member name is required.")
                else:
                    success, error = execute_query(
                        """
                        INSERT INTO members
                        (name, class_section, phone, email)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            name.strip(),
                            class_section.strip(),
                            phone.strip(),
                            email.strip()
                        )
                    )

                    if success:
                        st.success("Member added successfully!")
                        st.rerun()
                    else:
                        show_db_error(error)

    # ---------------- VIEW MEMBERS ----------------

    with tab2:
        st.subheader("Members and Outstanding Fine")

        members, error = get_members()

        if error:
            show_db_error(error)
        else:
            st.caption(
                f"Fine is automatically calculated at ₹{FINE_PER_DAY} per overdue day."
            )

            st.dataframe(
                members,
                use_container_width=True,
                hide_index=True
            )

            if not members.empty:
                total_fine = float(members["Fine (₹)"].sum())
                st.metric("💰 Total Outstanding Fine", f"₹{total_fine:.2f}")

    # ---------------- DELETE MEMBER ----------------

    with tab3:
        st.subheader("Delete a Member")

        members_raw, error = query_df("""
            SELECT member_id, name
            FROM members
            ORDER BY name
        """)

        if error:
            show_db_error(error)
        elif members_raw.empty:
            st.info("No members available to delete.")
        else:
            member_options = {
                f"{row['name']} (ID: {row['member_id']})": int(row["member_id"])
                for _, row in members_raw.iterrows()
            }

            selected = st.selectbox(
                "Select member",
                list(member_options.keys())
            )

            st.warning(
                "Deleting a member is permanent. A member with transaction history "
                "cannot be deleted because borrowing records must be preserved."
            )

            if st.button("🗑️ Delete Selected Member", type="secondary"):
                member_id = member_options[selected]

                history, history_error = query_df(
                    """
                    SELECT transaction_id
                    FROM transactions
                    WHERE member_id = %s
                    LIMIT 1
                    """,
                    (member_id,)
                )

                if history_error:
                    show_db_error(history_error)
                elif not history.empty:
                    st.error(
                        "This member has transaction history and cannot be deleted."
                    )
                else:
                    success, delete_error = execute_query(
                        "DELETE FROM members WHERE member_id = %s",
                        (member_id,)
                    )

                    if success:
                        st.success("Member deleted successfully.")
                        st.rerun()
                    else:
                        show_db_error(delete_error)


# ============================================================
# TRANSACTIONS
# ============================================================

elif page == "🔄 Transactions":

    st.title("🔄 Issue / Return Books")

    issue_tab, return_tab, history_tab = st.tabs([
        "📤 Issue Book",
        "📥 Return Book",
        "📋 Transaction History"
    ])

    # ---------------- ISSUE ----------------

    with issue_tab:
        st.subheader("Issue a Book")

        available_books, books_error = query_df("""
            SELECT book_id, title, available
            FROM books
            WHERE available > 0
            ORDER BY title
        """)

        members, members_error = query_df("""
            SELECT member_id, name
            FROM members
            ORDER BY name
        """)

        if books_error:
            show_db_error(books_error)
        elif members_error:
            show_db_error(members_error)
        elif available_books.empty:
            st.warning("No books are currently available.")
        elif members.empty:
            st.warning("No members are registered.")
        else:
            book_options = {
                f"{row['title']} (Available: {row['available']})":
                    int(row["book_id"])
                for _, row in available_books.iterrows()
            }

            member_options = {
                f"{row['name']} (ID: {row['member_id']})":
                    int(row["member_id"])
                for _, row in members.iterrows()
            }

            with st.form("issue_form"):
                selected_book = st.selectbox(
                    "Select Book",
                    list(book_options.keys())
                )

                selected_member = st.selectbox(
                    "Select Member",
                    list(member_options.keys())
                )

                issue_date = st.date_input(
                    "Issue Date",
                    value=date.today()
                )

                due_date = st.date_input(
                    "Due Date",
                    value=date.today()
                )

                submitted = st.form_submit_button("📤 Issue Book")

                if submitted:
                    book_id = book_options[selected_book]
                    member_id = member_options[selected_member]

                    if due_date < issue_date:
                        st.error("Due date cannot be before issue date.")
                    else:
                        success, error = execute_query(
                            """
                            INSERT INTO transactions
                            (book_id, member_id, issue_date, due_date)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (
                                book_id,
                                member_id,
                                issue_date,
                                due_date
                            )
                        )

                        if success:
                            update_success, update_error = execute_query(
                                """
                                UPDATE books
                                SET available = available - 1
                                WHERE book_id = %s
                                  AND available > 0
                                """,
                                (book_id,)
                            )

                            if update_success:
                                st.success("Book issued successfully!")
                                st.rerun()
                            else:
                                st.error(
                                    "Transaction created, but book availability "
                                    f"could not be updated: {update_error}"
                                )
                        else:
                            show_db_error(error)

    # ---------------- RETURN ----------------

    with return_tab:
        st.subheader("Return a Book")

        active, error = query_df("""
            SELECT
                t.transaction_id,
                t.book_id,
                t.member_id,
                b.title,
                m.name,
                t.issue_date,
                t.due_date
            FROM transactions t
            JOIN books b ON t.book_id = b.book_id
            JOIN members m ON t.member_id = m.member_id
            WHERE t.return_date IS NULL
            ORDER BY t.due_date
        """)

        if error:
            show_db_error(error)
        elif active.empty:
            st.info("There are no books currently issued.")
        else:
            options = {}

            for _, row in active.iterrows():
                options[
                    f"{row['title']} → {row['name']} "
                    f"(Due: {row['due_date']})"
                ] = int(row["transaction_id"])

            selected = st.selectbox(
                "Select transaction",
                list(options.keys())
            )

            return_date = st.date_input(
                "Return Date",
                value=date.today()
            )

            if st.button("📥 Return Book"):
                transaction_id = options[selected]

                row = active[
                    active["transaction_id"] == transaction_id
                ].iloc[0]

                due = row["due_date"]

                if hasattr(due, "date"):
                    due = due.date()

                fine = calculate_fine(due, return_date)

                update_success, update_error = execute_query(
                    """
                    UPDATE transactions
                    SET return_date = %s
                    WHERE transaction_id = %s
                    """,
                    (return_date, transaction_id)
                )

                if update_success:
                    book_update, book_error = execute_query(
                        """
                        UPDATE books
                        SET available = available + 1
                        WHERE book_id = %s
                        """,
                        (int(row["book_id"]),)
                    )

                    if book_update:
                        st.success("Book returned successfully.")

                        if fine > 0:
                            st.warning(
                                f"Late return. Fine: ₹{fine}"
                            )
                        else:
                            st.info("No fine for this return.")

                        st.rerun()
                    else:
                        st.error(
                            "Return recorded, but book availability could "
                            f"not be updated: {book_error}"
                        )
                else:
                    show_db_error(update_error)

    # ---------------- HISTORY ----------------

    with history_tab:
        st.subheader("Transaction History")

        transactions, error = get_transactions()

        if error:
            show_db_error(error)
        else:
            st.dataframe(
                transactions,
                use_container_width=True,
                hide_index=True
            )


# ============================================================
# ANALYTICS
# ============================================================

elif page == "📊 Analytics":

    st.title("📊 Library Analytics")

    books, books_error = get_books()
    transactions, transactions_error = get_transactions()
    members, members_error = get_members()

    if books_error:
        show_db_error(books_error)
        st.stop()

    if transactions_error:
        show_db_error(transactions_error)
        st.stop()

    if members_error:
        show_db_error(members_error)
        st.stop()

    # ---------------- CATEGORY ANALYSIS ----------------

    st.subheader("📚 Books by Category")

    if books.empty:
        st.info("No book data available.")
    else:
        category_data = (
            books.groupby("Category")["Quantity"]
            .sum()
            .sort_values(ascending=False)
        )

        fig, ax = plt.subplots(figsize=(9, 5))
        category_data.plot(kind="bar", ax=ax)
        ax.set_xlabel("Category")
        ax.set_ylabel("Number of Copies")
        ax.set_title("Books by Category")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    # ---------------- MOST BORROWED ----------------

    st.subheader("🏆 Most Borrowed Books")

    if transactions.empty:
        st.info("No borrowing data available.")
    else:
        borrowed = (
            transactions.groupby("Book")
            .size()
            .sort_values(ascending=False)
            .head(10)
        )

        fig, ax = plt.subplots(figsize=(9, 5))
        borrowed.plot(kind="bar", ax=ax)
        ax.set_xlabel("Book")
        ax.set_ylabel("Number of Transactions")
        ax.set_title("Most Borrowed Books")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    # ---------------- MONTHLY TREND ----------------

    st.subheader("📈 Monthly Issue Trend")

    if transactions.empty:
        st.info("No transaction data available.")
    else:
        trend = transactions.copy()
        trend["Issue Date"] = pd.to_datetime(trend["Issue Date"])

        monthly = (
            trend.groupby(
                trend["Issue Date"].dt.to_period("M")
            )
            .size()
        )

        monthly.index = monthly.index.astype(str)

        fig, ax = plt.subplots(figsize=(9, 5))
        monthly.plot(kind="line", marker="o", ax=ax)
        ax.set_xlabel("Month")
        ax.set_ylabel("Books Issued")
        ax.set_title("Monthly Library Issue Trend")
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    # ---------------- MEMBER ANALYSIS ----------------

    st.subheader("👥 Member Borrowing Analysis")

    if transactions.empty:
        st.info("No member borrowing data available.")
    else:
        member_borrowing = (
            transactions.groupby("Member")
            .size()
            .sort_values(ascending=False)
            .head(10)
        )

        fig, ax = plt.subplots(figsize=(9, 5))
        member_borrowing.plot(kind="bar", ax=ax)
        ax.set_xlabel("Member")
        ax.set_ylabel("Books Borrowed")
        ax.set_title("Top Borrowing Members")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    # ---------------- PANDAS SUMMARY ----------------

    st.subheader("📋 Pandas Data Analysis Summary")

    if not books.empty:
        summary = pd.DataFrame({
            "Metric": [
                "Total book titles",
                "Total copies",
                "Available copies",
                "Issued copies",
                "Registered members",
                "Total transactions"
            ],
            "Value": [
                len(books),
                int(books["Quantity"].sum()),
                int(books["Available"].sum()),
                int(books["Quantity"].sum() - books["Available"].sum()),
                len(members),
                len(transactions)
            ]
        })

        st.dataframe(
            summary,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# DATABASE
# ============================================================

elif page == "🗄️ Database":

    st.title("🗄️ Database Connection")

    connection, error = get_connection()

    if connection:
        st.success("✅ MySQL database connected successfully.")

        cfg = db_config()

        c1, c2, c3 = st.columns(3)
        c1.metric("Host", cfg["host"])
        c2.metric("Port", cfg["port"])
        c3.metric("Database", cfg["database"])

        connection.close()

    else:
        st.error("❌ MySQL connection failed.")
        st.code(str(error))

        st.info(
            "Check your .streamlit/secrets.toml file and make sure "
            "the MySQL Server service is running."
        )

    st.divider()

    st.subheader("Required Tables")

    tables, table_error = query_df("""
        SHOW TABLES
    """)

    if table_error:
        show_db_error(table_error)
    else:
        st.dataframe(
            tables,
            use_container_width=True,
            hide_index=True
        )

# ============================================================
# FOOTER
# ============================================================

st.sidebar.divider()
st.sidebar.caption("CBSE Class XII Informatics Practices")
st.sidebar.caption("Python • Pandas • Matplotlib • MySQL • Streamlit")
