"""Curated tech skills: canonical name -> (group, alias patterns).

Aliases are regular expressions matched case-insensitively against whole
tokens (see extract.py for the boundary rules). Ambiguous everyday words are
deliberately narrow: "Go" only matches "golang" or "go developer/engineer",
and single letters such as "R" or "C" are left out because job text uses them
for other things far more often than for the languages. Words that are also
everyday English ("react", "swift", "spring", "rails", "dart") match only in
their capitalised product form via a case-sensitive (?-i:...) group.
"""

LANGUAGES = "Languages"
FRONTEND = "Frontend"
BACKEND = "Backend"
MOBILE = "Mobile"
DATA = "Data"
AI = "AI & ML"
CLOUD = "Cloud & DevOps"
DATABASES = "Databases"
TESTING = "Testing & Quality"
PRACTICES = "Practices"
PLATFORMS = "Enterprise platforms"
SECURITY = "Security"

SKILLS: dict[str, tuple[str, list[str]]] = {
    # Languages
    "Python": (LANGUAGES, [r"python"]),
    "JavaScript": (LANGUAGES, [r"javascript", r"ecmascript"]),
    "TypeScript": (LANGUAGES, [r"typescript"]),
    "Java": (LANGUAGES, [r"java"]),
    "C#": (LANGUAGES, [r"c#", r"c sharp", r"csharp"]),
    "C++": (LANGUAGES, [r"c\+\+", r"cpp"]),
    "Go": (LANGUAGES, [r"golang", r"go (?:developer|engineer|programmer|programming)"]),
    "Rust": (LANGUAGES, [r"rust (?:developer|engineer|programming|language)", r"rustlang"]),
    "Kotlin": (LANGUAGES, [r"kotlin"]),
    "Swift": (LANGUAGES, [r"swift ?ui", r"(?-i:Swift)"]),
    "PHP": (LANGUAGES, [r"php"]),
    "Ruby": (LANGUAGES, [r"ruby"]),
    "Scala": (LANGUAGES, [r"scala"]),
    "SQL": (LANGUAGES, [r"sql", r"t-sql", r"pl/sql"]),
    "Bash": (LANGUAGES, [r"bash", r"shell scripting"]),
    "PowerShell": (LANGUAGES, [r"powershell"]),
    "Dart": (LANGUAGES, [r"(?-i:Dart)"]),
    # Frontend
    "React": (FRONTEND, [r"react\.?js", r"(?-i:React)"]),
    "Next.js": (FRONTEND, [r"next\.?js"]),
    "Angular": (FRONTEND, [r"angular(?:js)?"]),
    "Vue": (FRONTEND, [r"vue(?:\.?js)?"]),
    "Svelte": (FRONTEND, [r"svelte(?:kit)?"]),
    "HTML/CSS": (FRONTEND, [r"html5?", r"(?<!tailwind )css3?"]),
    "Tailwind CSS": (FRONTEND, [r"tailwind(?: ?css)?"]),
    "Redux": (FRONTEND, [r"redux"]),
    # Backend
    "Node.js": (BACKEND, [r"node\.?js"]),
    ".NET": (BACKEND, [r"\.net(?: core)?", r"dotnet", r"asp\.net"]),
    "Spring": (BACKEND, [r"spring ?boot", r"spring framework", r"(?-i:Spring)"]),
    "Django": (BACKEND, [r"django"]),
    "FastAPI": (BACKEND, [r"fastapi"]),
    "Flask": (BACKEND, [r"flask"]),
    "Express": (BACKEND, [r"express(?:\.?js)"]),
    "Laravel": (BACKEND, [r"laravel"]),
    "Ruby on Rails": (BACKEND, [r"ruby on rails", r"(?-i:Rails)"]),
    "GraphQL": (BACKEND, [r"graphql"]),
    "REST APIs": (BACKEND, [r"rest(?:ful)?(?: api| apis| services)", r"restful"]),
    "Microservices": (BACKEND, [r"micro-?services?"]),
    "Kafka": (BACKEND, [r"kafka"]),
    "RabbitMQ": (BACKEND, [r"rabbitmq"]),
    # Mobile
    "React Native": (MOBILE, [r"react native"]),
    "Flutter": (MOBILE, [r"flutter"]),
    "iOS": (MOBILE, [r"ios"]),
    "Android": (MOBILE, [r"android"]),
    # Databases
    "PostgreSQL": (DATABASES, [r"postgres(?:ql)?"]),
    "MySQL": (DATABASES, [r"mysql"]),
    "SQL Server": (DATABASES, [r"sql server", r"mssql"]),
    "Oracle": (DATABASES, [r"oracle"]),
    "MongoDB": (DATABASES, [r"mongo(?:db)?"]),
    "Redis": (DATABASES, [r"redis"]),
    "Elasticsearch": (DATABASES, [r"elastic ?search", r"opensearch"]),
    "DynamoDB": (DATABASES, [r"dynamo ?db"]),
    # Data
    "Snowflake": (DATA, [r"snowflake"]),
    "Databricks": (DATA, [r"databricks"]),
    "Spark": (DATA, [r"(?:apache )?spark", r"pyspark"]),
    "Airflow": (DATA, [r"airflow"]),
    "dbt": (DATA, [r"dbt"]),
    "Power BI": (DATA, [r"power ?bi"]),
    "Tableau": (DATA, [r"tableau"]),
    "pandas": (DATA, [r"pandas"]),
    "ETL": (DATA, [r"etl", r"elt", r"data pipelines?"]),
    "Data Warehousing": (DATA, [r"data ?warehous(?:e|ing)", r"data lake(?:house)?"]),
    # AI & ML
    "Machine Learning": (AI, [r"machine learning", r"ml engineer(?:ing)?"]),
    "Deep Learning": (AI, [r"deep learning"]),
    "LLMs": (AI, [r"llms?", r"large language models?", r"generative ai", r"gen ?ai"]),
    "NLP": (AI, [r"nlp", r"natural language processing"]),
    "Computer Vision": (AI, [r"computer vision"]),
    "PyTorch": (AI, [r"pytorch"]),
    "TensorFlow": (AI, [r"tensorflow"]),
    "scikit-learn": (AI, [r"scikit-?learn", r"sklearn"]),
    "RAG": (AI, [r"rag", r"retrieval[- ]augmented generation"]),
    "MLOps": (AI, [r"mlops"]),
    # Cloud & DevOps
    "AWS": (CLOUD, [r"aws", r"amazon web services"]),
    "Azure": (CLOUD, [r"azure"]),
    "GCP": (CLOUD, [r"gcp", r"google cloud(?: platform)?"]),
    "Docker": (CLOUD, [r"docker"]),
    "Kubernetes": (CLOUD, [r"kubernetes", r"k8s", r"aks", r"eks", r"gke"]),
    "Terraform": (CLOUD, [r"terraform"]),
    "Ansible": (CLOUD, [r"ansible"]),
    "CI/CD": (CLOUD, [r"ci ?/ ?cd", r"continuous (?:integration|delivery|deployment)"]),
    "GitHub Actions": (CLOUD, [r"github actions"]),
    "Azure DevOps": (CLOUD, [r"azure devops"]),
    "Jenkins": (CLOUD, [r"jenkins"]),
    "Linux": (CLOUD, [r"linux", r"ubuntu", r"red ?hat", r"rhel"]),
    "Serverless": (CLOUD, [r"serverless", r"lambda functions?", r"aws lambda", r"azure functions"]),
    "Infrastructure as Code": (CLOUD, [r"infrastructure as code", r"iac", r"cloudformation", r"bicep"]),
    "Observability": (CLOUD, [r"observability", r"datadog", r"grafana", r"prometheus", r"splunk", r"new relic"]),
    "Git": (CLOUD, [r"git"]),
    # Testing & Quality
    "Automated Testing": (TESTING, [r"test automation", r"automated testing", r"automation testing"]),
    "Selenium": (TESTING, [r"selenium"]),
    "Cypress": (TESTING, [r"cypress"]),
    "Playwright": (TESTING, [r"playwright"]),
    "Jest": (TESTING, [r"jest"]),
    "pytest": (TESTING, [r"pytest"]),
    "TDD": (TESTING, [r"tdd", r"test[- ]driven development"]),
    # Practices
    "Agile": (PRACTICES, [r"agile", r"scrum", r"kanban"]),
    "DevOps": (PRACTICES, [r"devops"]),
    "SRE": (PRACTICES, [r"sre", r"site reliability"]),
    "System Design": (PRACTICES, [r"system design", r"solution architecture", r"distributed systems"]),
    # Enterprise platforms
    "Salesforce": (PLATFORMS, [r"salesforce"]),
    "Dynamics 365": (PLATFORMS, [r"dynamics 365", r"d365", r"dynamics crm"]),
    "Power Platform": (PLATFORMS, [r"power platform", r"power apps", r"powerapps", r"power automate"]),
    "SAP": (PLATFORMS, [r"sap"]),
    "ServiceNow": (PLATFORMS, [r"servicenow"]),
    "SharePoint": (PLATFORMS, [r"sharepoint"]),
    # Security
    "Cyber Security": (SECURITY, [r"cyber ?security", r"information security", r"infosec"]),
    "IAM": (SECURITY, [r"iam", r"identity and access management", r"entra id", r"azure ad", r"okta"]),
    "OAuth": (SECURITY, [r"oauth2?", r"openid connect", r"oidc"]),
}
