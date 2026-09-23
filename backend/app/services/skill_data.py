"""Canonical skill taxonomy and default alias dictionary.

Admins extend/override aliases at runtime through the skill_aliases table —
no code change required. These seeds keep a fresh install useful.
"""

# normalized skill name -> category
SKILL_TAXONOMY: dict[str, str] = {
    # programming languages
    "Python": "programming_language", "Java": "programming_language",
    "JavaScript": "programming_language", "TypeScript": "programming_language",
    "C++": "programming_language", "C#": "programming_language",
    "Go": "programming_language", "Rust": "programming_language",
    "Ruby": "programming_language", "PHP": "programming_language",
    "Swift": "programming_language", "Kotlin": "programming_language",
    "R": "programming_language", "Scala": "programming_language",
    "SQL": "programming_language", "HTML": "programming_language",
    "CSS": "programming_language", "Bash": "programming_language",
    # frameworks & libraries
    "FastAPI": "framework", "Django": "framework", "Flask": "framework",
    "Spring Boot": "framework", "React": "framework", "Angular": "framework",
    "Vue.js": "framework", "Node.js": "framework", "Express": "framework",
    "Next.js": "framework", "TensorFlow": "framework", "PyTorch": "framework",
    "scikit-learn": "framework", "Pandas": "framework", "NumPy": "framework",
    "Keras": "framework", "Hugging Face": "framework", "LangChain": "framework",
    # databases
    "PostgreSQL": "database", "MySQL": "database", "MongoDB": "database",
    "Redis": "database", "SQLite": "database", "Oracle": "database",
    "Elasticsearch": "database", "Cassandra": "database", "DynamoDB": "database",
    # cloud & devops
    "AWS": "cloud", "Azure": "cloud", "GCP": "cloud",
    "Docker": "tool", "Kubernetes": "tool", "Terraform": "tool",
    "Jenkins": "tool", "Git": "tool", "GitHub": "tool", "GitLab": "tool",
    "CI/CD": "tool", "Linux": "tool", "Nginx": "tool", "Kafka": "tool",
    "Celery": "tool", "Airflow": "tool",
    # data & AI
    "Machine Learning": "domain", "Deep Learning": "domain", "NLP": "domain",
    "Computer Vision": "domain", "Data Analysis": "domain",
    "Data Engineering": "domain", "MLOps": "domain", "LLM": "domain",
    "Statistics": "domain", "ETL": "domain", "Spark": "tool",
    "Hadoop": "tool", "Tableau": "tool", "Power BI": "tool",
    # methodologies & soft skills
    "Agile": "methodology", "Scrum": "methodology", "REST": "methodology",
    "GraphQL": "methodology", "Microservices": "methodology",
    "Communication": "soft_skill", "Leadership": "soft_skill",
    "Problem Solving": "soft_skill", "Teamwork": "soft_skill",
}

# alias (lowercase) -> canonical name; seeds for the skill_aliases table
DEFAULT_SKILL_ALIASES: dict[str, str] = {
    "python programming": "Python", "python3": "Python",
    "postgres": "PostgreSQL", "postgre sql": "PostgreSQL",
    "postgresql db": "PostgreSQL", "psql": "PostgreSQL",
    "amazon web services": "AWS", "aws cloud": "AWS",
    "react.js": "React", "reactjs": "React", "react js": "React",
    "node js": "Node.js", "nodejs": "Node.js", "node": "Node.js",
    "vue": "Vue.js", "vuejs": "Vue.js", "vue.js": "Vue.js",
    "google cloud": "GCP", "google cloud platform": "GCP",
    "ms azure": "Azure", "microsoft azure": "Azure",
    "k8s": "Kubernetes", "kube": "Kubernetes",
    "sklearn": "scikit-learn", "scikit learn": "scikit-learn",
    "ml": "Machine Learning", "machine learning": "Machine Learning",
    "natural language processing": "NLP",
    "js": "JavaScript", "javascript/es6": "JavaScript",
    "ts": "TypeScript", "golang": "Go", "cpp": "C++",
    "mongo": "MongoDB", "express.js": "Express", "expressjs": "Express",
    "spring": "Spring Boot", "springboot": "Spring Boot",
    "nextjs": "Next.js", "next js": "Next.js",
    "ci / cd": "CI/CD", "cicd": "CI/CD",
    "deep learning": "Deep Learning", "dl": "Deep Learning",
    "powerbi": "Power BI", "elastic search": "Elasticsearch",
    "mysql db": "MySQL", "ms sql": "SQL",
}
