import json
from typing import Any, Optional

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from src.config.settings import settings
from src.utils.logger import logger

class LLMClient:
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
    def parse_intent(
        self,
        user_message: str,
        system_prompt: str,
        response_model: type[BaseModel],
        max_retries: int = 2
    ) -> Optional[BaseModel]:
        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                content = response.choices[0].message.content
                if not content:
                    logger.error("Empty response from LLM")
                    continue
                
                data = json.loads(content)
                result = response_model.model_validate(data)
                
                logger.debug(f"Intent parsed successfully: {result}")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to decode JSON (attempt {attempt + 1}): {e}")
            except ValidationError as e:
                logger.warning(f"Validation error (attempt {attempt + 1}): {e}")
            except Exception as e:
                logger.error(f"Unexpected error in LLM parsing: {e}")
                break
        
        logger.error("Failed to parse intent after all retries")
        return None
    
    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> Optional[str]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            return None
