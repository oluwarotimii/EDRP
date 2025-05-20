import httpx
import json
import logging
from typing import Dict, Any, Optional
import os

from app.config import settings

logger = logging.getLogger(__name__)

PAYSTACK_SECRET_KEY = settings.PAYSTACK_SECRET_KEY
PAYSTACK_BASE_URL = "https://api.paystack.co"

async def initialize_payment(
    email: str, 
    amount: float, 
    callback_url: Optional[str] = None,
    reference: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Initialize a payment transaction with Paystack.
    
    Args:
        email: Customer's email address
        amount: Amount to charge in the actual currency (e.g., naira)
        callback_url: URL to redirect to after payment
        reference: Unique transaction reference (if not provided, Paystack generates one)
        metadata: Additional data to store with the transaction
        description: Description of the transaction
        
    Returns:
        Dict containing transaction details including authorization_url
    """
    if not PAYSTACK_SECRET_KEY:
        logger.error("Paystack secret key not configured")
        raise ValueError("Payment gateway is not properly configured")
    
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    # Convert amount to kobo (Paystack uses the smallest currency unit)
    amount_in_kobo = int(amount * 100)
    
    payload = {
        "email": email,
        "amount": amount_in_kobo,
    }
    
    if callback_url:
        payload["callback_url"] = callback_url
    
    if reference:
        payload["reference"] = reference
    
    if metadata:
        payload["metadata"] = metadata
    
    if description:
        payload["description"] = description
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYSTACK_BASE_URL}/transaction/initialize",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("status"):
                return response_data["data"]
            else:
                logger.error(f"Paystack initialization failed: {response_data}")
                raise ValueError(f"Payment initialization failed: {response_data.get('message', 'Unknown error')}")
    
    except httpx.RequestError as e:
        logger.error(f"Error initializing Paystack payment: {str(e)}")
        raise ValueError(f"Payment service connection error: {str(e)}")

async def verify_payment(reference: str) -> Dict[str, Any]:
    """
    Verify a payment transaction with Paystack.
    
    Args:
        reference: The transaction reference to verify
        
    Returns:
        Dict containing transaction details and verification status
    """
    if not PAYSTACK_SECRET_KEY:
        logger.error("Paystack secret key not configured")
        raise ValueError("Payment gateway is not properly configured")
    
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
                headers=headers,
                timeout=30.0
            )
            
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("status"):
                data = response_data["data"]
                
                # Extract metadata
                metadata = data.get("metadata", {})
                
                # Create a simplified result
                result = {
                    "status": data.get("status") == "success",
                    "amount": data.get("amount"),
                    "reference": data.get("reference"),
                    "transaction_date": data.get("paid_at"),
                    "metadata": metadata
                }
                
                return result
            else:
                logger.error(f"Paystack verification failed: {response_data}")
                return {
                    "status": False,
                    "message": response_data.get("message", "Verification failed")
                }
    
    except httpx.RequestError as e:
        logger.error(f"Error verifying Paystack payment: {str(e)}")
        return {
            "status": False,
            "message": f"Payment verification failed: {str(e)}"
        }
