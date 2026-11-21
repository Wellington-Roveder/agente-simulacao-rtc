# Regras do projeto

- Utilize Python 3.12 ou superior.
- Utilize FastAPI para a API backend.
- Utilize Pydantic v2 para validação e serialização de dados.
- Utilize httpx assíncrono para chamadas HTTP externas.
- Utilize Redis para cache e armazenamento temporário.
- Utilize o OpenAI SDK para integrações com modelos LLM.
- Utilize Ruff para linting e formatação.
- Utilize pytest para os testes.
- Nunca delegue cálculos fiscais ao LLM; os cálculos devem ser realizados exclusivamente pelos contêineres oficiais da Receita Federal.
- Antes de qualquer chamada externa, aplique a anonimização exigida pela LGPD aos dados pessoais.
