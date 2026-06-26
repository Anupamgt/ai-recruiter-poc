"""Synthetic resume generator for PoC stress testing."""
import os


SYNTHETIC_RESUMES = [
    ("alex_cloud_architect.txt", """Alex Mercer
Senior Cloud Architect & Systems Engineer
Experience:
2018 - Present: Lead Cloud Architect at TechCorp. Spearheaded migration of 50+ microservices to AWS Kubernetes. Managed $2M cloud budget. Mentored team of 12 engineers.
2015 - 2018: Senior DevOps Engineer at CloudScale. Automated CI/CD pipelines using Terraform and Jenkins.
Education: Master of Science in Computer Science, Stanford University.
Skills: AWS, Kubernetes, Terraform, Python, Go, Docker, Distributed Systems."""),
    
    ("samantha_data_scientist.txt", """Dr. Samantha Vance
Principal AI & Machine Learning Scientist
Experience:
2019 - Present: Head of AI at DataMind. Architected LLM RAG pipelines and multimodal recommendation models. Grew AI research division from 2 to 15 researchers.
2016 - 2019: Senior Data Scientist at DeepLearn Inc. Spearheaded computer vision projects.
Education: Ph.D. in Machine Learning, MIT. Bachelor of Science in Mathematics.
Skills: PyTorch, Python, TensorFlow, Transformers, Deep Learning, SQL, LLM Agents."""),

    ("marcus_backend_dev.txt", """Marcus Brody
Senior Backend Developer
Experience:
2020 - Present: Staff Software Engineer at FinTech Global. Built high-throughput transaction processing microservices handling 10k QPS. Owned payment gateway integration.
2017 - 2020: Software Engineer at WebWorks. Developed REST APIs using Django and PostgreSQL.
Education: Bachelor of Science in Software Engineering, UC Berkeley.
Skills: Python, FastAPI, PostgreSQL, Redis, Kafka, Docker, Git.""")
]


def main():
    target_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sample_resumes")
    os.makedirs(target_dir, exist_ok=True)
    
    for filename, content in SYNTHETIC_RESUMES:
        path = os.path.join(target_dir, filename)
        with open(path, "w") as f:
            f.write(content)
        print(f"Generated synthetic resume: {path}")


if __name__ == "__main__":
    main()
