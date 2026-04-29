DEFAULT_PASSWORD = "Hackathon123!"

ADMIN_GROUP = "admin"
EMPLOYEE_GROUP = "employee"
CUSTOMER_GROUP = "customer"

BANK_USERS = [
    {
        "username": "bank.admin@example.com",
        "password": DEFAULT_PASSWORD,
        "group": ADMIN_GROUP,
        "role": "bank_admin",
        "name": "Priya Shah",
        "title": "Bank Access Administrator",
        "department": "Identity and Access Governance",
        "is_human": True,
    },
    {
        "username": "bank.analyst@example.com",
        "password": DEFAULT_PASSWORD,
        "group": EMPLOYEE_GROUP,
        "role": "bank_analyst",
        "name": "Marcus Lee",
        "title": "Banking Operations Analyst",
        "department": "Operations Analytics",
        "is_human": True,
    },
    {
        "username": "bank.customer@example.com",
        "password": DEFAULT_PASSWORD,
        "group": CUSTOMER_GROUP,
        "role": "retail_customer",
        "name": "Emily Carter",
        "title": "Retail Banking Customer",
        "department": "External Customer",
        "is_human": True,
        "customer_id": "CUST-1001",
    },
    {
        "username": "it.support@example.com",
        "password": DEFAULT_PASSWORD,
        "group": EMPLOYEE_GROUP,
        "role": "it_support",
        "name": "Noah Patel",
        "title": "IT Support Engineer",
        "department": "Technology Support",
        "is_human": True,
    },
]

OLD_DEMO_USERNAMES = [
    "admin@example.com",
    "employee1@example.com",
    "analyst@example.com",
    "customer@example.com",
    "live.agent.created.1777440998@example.com",
]

BANK_POLICIES = {
    "bank.admin@example.com": (
        "Priya Shah is a bank identity and access administrator. She may create "
        "Cognito application users, add users to approved groups, maintain the "
        "users-table principal directory, and create, review, update, or delete "
        "policy-table access policies for bank employees and service accounts. "
        "She may request temporary access only for bank user onboarding, access "
        "governance, break-glass access review, or policy administration work. "
        "Grant the minimum required access and deny unrelated customer banking "
        "data access unless the reason is explicitly tied to an access review."
    ),
    "bank.analyst@example.com": (
        "Marcus Lee is a banking operations analyst. He may review aggregate "
        "bank operational metrics and transaction ledger records for portfolio "
        "health, fraud trend analysis, card spend reporting, deposit movement "
        "reporting, branch operations, and finance operations questions. He is "
        "not a customer support worker and must not receive broad customer PII, "
        "KYC profile, balance, Cognito, users-table write, or policy-table "
        "access."
    ),
    "bank.customer@example.com": (
        "Emily Carter is an external retail banking customer. She may access "
        "only her own bank balance and her own transaction history for customer "
        "self-service. Her access must be scoped to her signed-in user_id and "
        "must not include other customer profiles, operational metrics, policy "
        "data, Cognito, users-table administration, or employee-only records."
    ),
    "it.support@example.com": (
        "Noah Patel is an IT support engineer for the bank. He may inspect "
        "customer profile, account balance, and transaction records only when "
        "working an assigned IT or customer support ticket involving login "
        "issues, account authorisation checks, disputed access, card support, "
        "or customer account troubleshooting. He may update support notes or "
        "operational status fields when the ticket requires it. He is not an "
        "access administrator and must not receive policy-table, Cognito user "
        "management, users-table write, or broad operational metrics access."
    ),
}

BANK_CUSTOMER_PROFILES = [
    {
        "customer_id": "CUST-1001",
        "name": "Emily Carter",
        "email": "bank.customer@example.com",
        "segment": "Everyday Banking",
        "kyc_status": "verified",
        "risk_tier": "low",
        "relationship_manager": "Sophie Nguyen",
        "primary_account_id": "ACC-1001-CHK",
        "mobile_phone": "+61-400-010-001",
        "address_city": "Sydney",
        "support_note": "Prefers mobile push notifications for card alerts.",
    },
    {
        "customer_id": "CUST-1002",
        "name": "Daniel Wright",
        "email": "daniel.wright@example.com",
        "segment": "Premier",
        "kyc_status": "verified",
        "risk_tier": "medium",
        "relationship_manager": "Amelia Jones",
        "primary_account_id": "ACC-1002-CHK",
        "mobile_phone": "+61-400-010-002",
        "address_city": "Melbourne",
        "support_note": "Open card replacement ticket SR-48219.",
    },
    {
        "customer_id": "CUST-1003",
        "name": "Aisha Khan",
        "email": "aisha.khan@example.com",
        "segment": "Small Business",
        "kyc_status": "enhanced_review",
        "risk_tier": "medium",
        "relationship_manager": "Oliver Brown",
        "primary_account_id": "ACC-1003-BUS",
        "mobile_phone": "+61-400-010-003",
        "address_city": "Brisbane",
        "support_note": "Business banking authority change pending.",
    },
    {
        "customer_id": "CUST-1004",
        "name": "Olivia Martin",
        "email": "olivia.martin@example.com",
        "segment": "Home Lending",
        "kyc_status": "verified",
        "risk_tier": "low",
        "relationship_manager": "Ethan Wilson",
        "primary_account_id": "ACC-1004-OFFSET",
        "mobile_phone": "+61-400-010-004",
        "address_city": "Perth",
        "support_note": "Mortgage offset account linked in March 2026.",
    },
    {
        "customer_id": "CUST-1005",
        "name": "Thomas Nguyen",
        "email": "thomas.nguyen@example.com",
        "segment": "Everyday Banking",
        "kyc_status": "verified",
        "risk_tier": "high",
        "relationship_manager": "Mia Taylor",
        "primary_account_id": "ACC-1005-CHK",
        "mobile_phone": "+61-400-010-005",
        "address_city": "Adelaide",
        "support_note": "Recent fraud alert reviewed and card reissued.",
    },
    {
        "customer_id": "CUST-1006",
        "name": "Sofia Rossi",
        "email": "sofia.rossi@example.com",
        "segment": "Wealth",
        "kyc_status": "verified",
        "risk_tier": "low",
        "relationship_manager": "Charlotte Davis",
        "primary_account_id": "ACC-1006-SAV",
        "mobile_phone": "+61-400-010-006",
        "address_city": "Canberra",
        "support_note": "Requested term deposit maturity options.",
    },
]

BANK_BALANCES_TEMPLATE = [
    {
        "customer_id": "CUST-1001",
        "accounts": [
            {
                "account_id": "ACC-1001-CHK",
                "account_type": "Everyday Account",
                "bsb": "062-001",
                "available_balance": "4827.35",
                "current_balance": "4932.10",
                "currency": "AUD",
                "status": "open",
            },
            {
                "account_id": "ACC-1001-SAV",
                "account_type": "Goal Saver",
                "bsb": "062-001",
                "available_balance": "18420.00",
                "current_balance": "18420.00",
                "currency": "AUD",
                "status": "open",
            },
        ],
        "overdraft_status": "not_enabled",
        "last_statement_date": "2026-04-15",
    }
]

BANK_TRANSACTIONS_TEMPLATE = [
    {
        "transaction_id": "TXN-1001-0001",
        "customer_id": "CUST-1001",
        "account_id": "ACC-1001-CHK",
        "posted_at": "2026-04-28T09:14:22Z",
        "description": "Payroll deposit - Harper Finch Pty Ltd",
        "merchant": "Harper Finch Pty Ltd",
        "channel": "direct_credit",
        "amount": "4250.00",
        "currency": "AUD",
        "direction": "credit",
        "status": "posted",
        "risk_signal": "none",
    },
    {
        "transaction_id": "TXN-1001-0002",
        "customer_id": "CUST-1001",
        "account_id": "ACC-1001-CHK",
        "posted_at": "2026-04-27T18:41:10Z",
        "description": "Card purchase - Woolworths Town Hall",
        "merchant": "Woolworths",
        "channel": "card_present",
        "amount": "-86.45",
        "currency": "AUD",
        "direction": "debit",
        "status": "posted",
        "risk_signal": "none",
    },
    {
        "transaction_id": "TXN-1001-0003",
        "customer_id": "CUST-1001",
        "account_id": "ACC-1001-CHK",
        "posted_at": "2026-04-26T07:32:54Z",
        "description": "Osko transfer to Liam Carter",
        "merchant": "PayID Transfer",
        "channel": "osko",
        "amount": "-250.00",
        "currency": "AUD",
        "direction": "debit",
        "status": "posted",
        "risk_signal": "none",
    },
    {
        "transaction_id": "TXN-1001-0004",
        "customer_id": "CUST-1001",
        "account_id": "ACC-1001-SAV",
        "posted_at": "2026-04-25T01:12:00Z",
        "description": "Monthly saver interest",
        "merchant": "Bank Interest",
        "channel": "system",
        "amount": "42.17",
        "currency": "AUD",
        "direction": "credit",
        "status": "posted",
        "risk_signal": "none",
    },
    {
        "transaction_id": "TXN-1001-0005",
        "customer_id": "CUST-1001",
        "account_id": "ACC-1001-CHK",
        "posted_at": "2026-04-23T21:06:45Z",
        "description": "Card purchase - Qantas Airways",
        "merchant": "Qantas Airways",
        "channel": "card_not_present",
        "amount": "-612.30",
        "currency": "AUD",
        "direction": "debit",
        "status": "posted",
        "risk_signal": "travel_pattern_match",
    },
    {
        "transaction_id": "TXN-1001-0006",
        "customer_id": "CUST-1001",
        "account_id": "ACC-1001-CHK",
        "posted_at": "2026-04-22T11:18:03Z",
        "description": "ATM withdrawal - Sydney CBD",
        "merchant": "Bank ATM",
        "channel": "atm",
        "amount": "-120.00",
        "currency": "AUD",
        "direction": "debit",
        "status": "posted",
        "risk_signal": "none",
    },
    {
        "transaction_id": "TXN-1001-0007",
        "customer_id": "CUST-1001",
        "account_id": "ACC-1001-CHK",
        "posted_at": "2026-04-21T15:55:14Z",
        "description": "Card reversal - Online retailer",
        "merchant": "North Star Retail",
        "channel": "card_not_present",
        "amount": "39.95",
        "currency": "AUD",
        "direction": "credit",
        "status": "posted",
        "risk_signal": "none",
    },
]

BANK_OPERATIONAL_METRICS = [
    {
        "metric_id": "DEP-2026-04",
        "metric_name": "retail_deposits",
        "period": "2026-04",
        "segment": "retail",
        "value": "1842500000",
        "unit": "AUD",
        "trend": "up_2_4_percent",
    },
    {
        "metric_id": "CARD-2026-04",
        "metric_name": "card_purchase_volume",
        "period": "2026-04",
        "segment": "consumer_cards",
        "value": "412870000",
        "unit": "AUD",
        "trend": "up_4_1_percent",
    },
    {
        "metric_id": "FRAUD-2026-04",
        "metric_name": "confirmed_card_fraud_rate",
        "period": "2026-04",
        "segment": "consumer_cards",
        "value": "0.031",
        "unit": "percent",
        "trend": "down_0_004_points",
    },
    {
        "metric_id": "NPL-2026-Q1",
        "metric_name": "non_performing_loan_ratio",
        "period": "2026-Q1",
        "segment": "home_lending",
        "value": "0.82",
        "unit": "percent",
        "trend": "flat",
    },
    {
        "metric_id": "BRANCH-2026-04-SYD",
        "metric_name": "branch_service_volume",
        "period": "2026-04",
        "segment": "sydney_metro",
        "value": "42891",
        "unit": "interactions",
        "trend": "up_1_8_percent",
    },
]
