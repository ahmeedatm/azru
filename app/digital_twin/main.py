import asyncio
import logging
from app.digital_twin.simulator import Simulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DigitalTwin")

async def main():
    logger.info("Starting Digital Twin Simulator...")
    # Initialize simulator with default scenario (can be env var later)
    sim = Simulator()
    
    try:
        await sim.run()
    except Exception as e:
        logger.error(f"Simulator crashed: {e}")
        # Optional: Restart logic or exit
        
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Simulator stopped by user.")
