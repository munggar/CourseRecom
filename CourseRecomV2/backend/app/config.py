import hmac
import ipaddress
import json
import os
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = 'CourseRecom'
    environment: str = 'development'
    database_url: str = 'sqlite:///./courserecom.db'
    jwt_secret: str = 'course-recom-dev-secret-change-me'
    qr_verification_secret: str = 'course-recom-dev-qr-secret-change-me'
    gemini_api_key: str = ''
    gemini_model: str = 'gemini-2.0-flash-lite'
    frontend_url: str = 'http://localhost:5173'
    public_api_base_url: str | None = None
    seed_demo_users: bool | None = None
    bootstrap_admin_nim: str | None = None
    bootstrap_admin_name: str | None = None
    bootstrap_admin_password: str | None = None
    recommendation_weights: str = '{"similar_students":0.30,"academic_history":0.25,"interest":0.20,"curriculum":0.15,"course_pattern":0.10}'
    passing_grades: str = 'A,A-,B+,B,B-,C+,C,C-,D'
    total_curriculum_sks: int = 144

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    @model_validator(mode='after')
    def normalize_database_url(self):
        parsed = urlparse(self.database_url)
        is_containerized = os.path.exists('/.dockerenv') or os.environ.get('DOTNET_RUNNING_IN_CONTAINER') == 'true'

        if parsed.scheme in {'postgres', 'postgresql'}:
            self.database_url = self.database_url.replace(
                f'{parsed.scheme}://',
                'postgresql+psycopg://',
                1,
            )
            parsed = urlparse(self.database_url)

        bootstrap_values = (
            self.bootstrap_admin_nim,
            self.bootstrap_admin_name,
            self.bootstrap_admin_password,
        )
        if any(bootstrap_values) and not all(bootstrap_values):
            raise ValueError(
                'BOOTSTRAP_ADMIN_NIM, BOOTSTRAP_ADMIN_NAME, and '
                'BOOTSTRAP_ADMIN_PASSWORD must be configured together'
            )

        demo_seed_environments = {'development', 'dev', 'testing', 'test'}
        if self.seed_demo_users is None:
            self.seed_demo_users = self.environment.casefold() in demo_seed_environments
        elif self.seed_demo_users and self.environment.casefold() not in demo_seed_environments:
            raise ValueError('SEED_DEMO_USERS may only be enabled in development or testing')

        if (
            not is_containerized
            and parsed.scheme.startswith('postgres')
            and parsed.hostname == 'db'
        ):
            self.database_url = 'sqlite:///./courserecom.db'
        production = self.environment.casefold() in {'prod', 'production'}
        if production and self.jwt_secret == 'course-recom-dev-secret-change-me':
            raise ValueError('JWT_SECRET must be explicitly configured in production')
        if production and self.qr_verification_secret == 'course-recom-dev-qr-secret-change-me':
            raise ValueError('QR_VERIFICATION_SECRET must be explicitly configured in production')
        if production and self.seed_demo_users:
            raise ValueError('SEED_DEMO_USERS must be false in production')
        if production and len(self.jwt_secret) < 32:
            raise ValueError('JWT_SECRET must contain at least 32 characters in production')
        if production and len(self.qr_verification_secret) < 32:
            raise ValueError('QR_VERIFICATION_SECRET must contain at least 32 characters in production')
        if production and hmac.compare_digest(self.jwt_secret, self.qr_verification_secret):
            raise ValueError('JWT_SECRET and QR_VERIFICATION_SECRET must be different')
        if production:
            public_api = urlparse(self.public_api_base_url or '')
            host = (public_api.hostname or '').rstrip('.').casefold()
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if (
                public_api.scheme != 'https'
                or not public_api.hostname
                or public_api.username
                or public_api.password
                or public_api.query
                or public_api.fragment
                or not public_api.path.rstrip('/').endswith('/api')
                or host in {
                    'backend',
                    'db',
                    'postgres',
                    'frontend',
                    'localhost',
                    'localhost.localdomain',
                }
                or host.endswith(('.internal', '.local', '.localhost'))
                or (address is not None and not address.is_global)
            ):
                raise ValueError(
                    'PUBLIC_API_BASE_URL must be an HTTPS URL ending in /api in production'
                )
        return self

    def get_recommendation_weights(self) -> dict[str, float]:
        weights = json.loads(self.recommendation_weights)
        required = {'similar_students', 'academic_history', 'interest', 'curriculum', 'course_pattern'}
        if set(weights) != required or any(float(value) < 0 for value in weights.values()):
            raise ValueError('RECOMMENDATION_WEIGHTS must define five non-negative model weights')
        total = sum(float(value) for value in weights.values())
        if total <= 0:
            raise ValueError('RECOMMENDATION_WEIGHTS must have a positive total')
        return {key: float(value) / total for key, value in weights.items()}

    def get_passing_grades(self) -> set[str]:
        grades = {grade.strip().upper() for grade in self.passing_grades.split(',') if grade.strip()}
        if not grades or not grades.issubset({'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D'}):
            raise ValueError('PASSING_GRADES must be a non-empty list of valid passing grades')
        return grades


settings = Settings()
