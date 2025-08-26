import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from openai_extraction_agent import OpenAIExtractionAgent
from openai_form_filling_agent import OpenAIFormFillingAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAIAgentCoordinator:
    """
    Coordinator that manages the two-agent workflow:
    1. Extraction Agent: Extracts data from documents and saves to JSON
    2. Form Filling Agent: Reads JSON data and fills PDF forms
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the coordinator with both agents
        
        Args:
            api_key: OpenAI API key. If None, will try to get from environment variable
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        # Initialize both agents
        self.extraction_agent = OpenAIExtractionAgent(api_key=self.api_key)
        self.form_filling_agent = OpenAIFormFillingAgent(api_key=self.api_key)
        
        # Create coordinator output directory
        self.output_dir = "coordinator_output"
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info("OpenAI Agent Coordinator initialized with both extraction and form filling agents")
    
    def extract_and_fill_workflow(self, document_paths: List[str], form_paths: List[str]) -> Dict[str, Any]:
        """
        Complete two-agent workflow: extract data from documents, then fill forms
        
        Args:
            document_paths: List of document paths to extract data from
            form_paths: List of PDF form paths to fill
            
        Returns:
            Dictionary containing complete workflow results
        """
        try:
            logger.info(f"Starting two-agent workflow: {len(document_paths)} documents → {len(form_paths)} forms")
            
            workflow_start_time = datetime.now()
            
            # Step 1: Extract data from documents using Extraction Agent
            logger.info("Step 1: Extracting data from documents...")
            if len(document_paths) == 1:
                extraction_result = self.extraction_agent.extract_from_document(document_paths[0])
                if not extraction_result["success"]:
                    return {
                        "success": False,
                        "error": f"Extraction failed: {extraction_result['error']}",
                        "stage": "extraction"
                    }
                json_path = extraction_result["json_file_path"]
                extraction_summary = extraction_result["extraction_summary"]
            else:
                extraction_result = self.extraction_agent.extract_from_multiple_documents(document_paths)
                if not extraction_result["success"]:
                    return {
                        "success": False,
                        "error": "Extraction failed for all documents",
                        "stage": "extraction",
                        "extraction_details": extraction_result
                    }
                json_path = extraction_result["combined_json_path"]
                extraction_summary = {
                    "total_fields": self.extraction_agent._count_non_null_fields(extraction_result["combined_data"]),
                    "successful_extractions": extraction_result["successful_extractions"],
                    "failed_extractions": extraction_result["failed_extractions"]
                }
            
            logger.info(f"✅ Extraction completed. Data saved to: {json_path}")
            
            # Step 2: Fill forms using Form Filling Agent
            logger.info("Step 2: Filling PDF forms with extracted data...")
            if len(form_paths) == 1:
                filling_result = self.form_filling_agent.fill_form_from_json(form_paths[0], json_path)
                filling_results = [filling_result]
            else:
                batch_result = self.form_filling_agent.fill_multiple_forms(form_paths, json_path)
                filling_results = batch_result["individual_results"]
                filling_result = batch_result
            
            # Count successful form fills
            successful_fills = sum(1 for result in filling_results if result.get("success", False))
            failed_fills = len(filling_results) - successful_fills
            
            logger.info(f"✅ Form filling completed. {successful_fills}/{len(form_paths)} forms filled successfully")
            
            # Step 3: Generate comprehensive workflow report
            workflow_end_time = datetime.now()
            workflow_duration = (workflow_end_time - workflow_start_time).total_seconds()
            
            # Collect filled form paths
            filled_form_paths = []
            for result in filling_results:
                if result.get("success") and "output_pdf" in result:
                    filled_form_paths.append(result["output_pdf"])
            
            # Create workflow summary
            workflow_result = {
                "success": successful_fills > 0,
                "workflow_summary": {
                    "total_documents_processed": len(document_paths),
                    "total_forms_processed": len(form_paths),
                    "successful_form_fills": successful_fills,
                    "failed_form_fills": failed_fills,
                    "workflow_duration_seconds": workflow_duration,
                    "extraction_data_file": json_path,
                    "filled_form_paths": filled_form_paths
                },
                "extraction_results": {
                    "success": extraction_result["success"],
                    "summary": extraction_summary,
                    "json_file": json_path
                },
                "form_filling_results": {
                    "success": successful_fills > 0,
                    "individual_results": filling_results,
                    "summary": {
                        "successful_fills": successful_fills,
                        "failed_fills": failed_fills,
                        "fill_rate": (successful_fills / len(form_paths)) * 100 if form_paths else 0
                    }
                },
                "timestamp": datetime.now().isoformat(),
                "agent_info": {
                    "extraction_agent": "OpenAI Extraction Agent",
                    "form_filling_agent": "OpenAI Form Filling Agent",
                    "model_used": self.extraction_agent.model
                }
            }
            
            # Save workflow report
            report_path = self.save_workflow_report(workflow_result)
            workflow_result["workflow_report_path"] = report_path
            
            return workflow_result
            
        except Exception as e:
            logger.error(f"Workflow failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "stage": "workflow_coordination",
                "timestamp": datetime.now().isoformat()
            }
    
    def extract_data_only(self, document_paths: List[str]) -> Dict[str, Any]:
        """
        Extract data from documents only (for Step 1 of the frontend workflow)
        
        Args:
            document_paths: List of document paths to extract data from
            
        Returns:
            Dictionary containing extraction results
        """
        try:
            logger.info(f"Extracting data from {len(document_paths)} documents")
            
            if len(document_paths) == 1:
                result = self.extraction_agent.extract_from_document(document_paths[0])
            else:
                result = self.extraction_agent.extract_from_multiple_documents(document_paths)
            
            return result
            
        except Exception as e:
            logger.error(f"Data extraction failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def fill_forms_with_json(self, form_paths: List[str], json_path: str) -> Dict[str, Any]:
        """
        Fill forms using existing JSON data (for Step 2 of the frontend workflow)
        
        Args:
            form_paths: List of PDF form paths to fill
            json_path: Path to JSON file with extracted data
            
        Returns:
            Dictionary containing form filling results
        """
        try:
            logger.info(f"Filling {len(form_paths)} forms with data from {json_path}")
            
            if len(form_paths) == 1:
                result = self.form_filling_agent.fill_form_from_json(form_paths[0], json_path)
                return {
                    "success": result["success"],
                    "individual_results": [result],
                    "summary": {
                        "successful_fills": 1 if result["success"] else 0,
                        "failed_fills": 0 if result["success"] else 1,
                        "total_forms": 1
                    }
                }
            else:
                result = self.form_filling_agent.fill_multiple_forms(form_paths, json_path)
                return result
                
        except Exception as e:
            logger.error(f"Form filling failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def preview_form_mapping(self, form_path: str, json_path: str) -> Dict[str, Any]:
        """
        Preview how extracted data would be mapped to form fields
        
        Args:
            form_path: Path to PDF form
            json_path: Path to JSON file with extracted data
            
        Returns:
            Dictionary containing mapping preview
        """
        try:
            return self.form_filling_agent.preview_field_mapping(form_path, json_path)
        except Exception as e:
            logger.error(f"Preview generation failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def save_workflow_report(self, workflow_result: Dict[str, Any]) -> str:
        """
        Save comprehensive workflow report to JSON file
        
        Args:
            workflow_result: Complete workflow results
            
        Returns:
            Path to saved report file
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"workflow_report_{timestamp}.json"
            report_path = os.path.join(self.output_dir, report_filename)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(workflow_result, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Workflow report saved to: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Error saving workflow report: {str(e)}")
            return ""
    
    def get_extraction_data_from_json(self, json_path: str) -> Dict[str, Any]:
        """
        Load and return extracted data from JSON file for frontend display
        
        Args:
            json_path: Path to JSON file with extracted data
            
        Returns:
            Extracted data dictionary
        """
        try:
            return self.form_filling_agent.load_extracted_data(json_path)
        except Exception as e:
            logger.error(f"Error loading extracted data: {str(e)}")
            return {}
    
    def create_zip_archive(self, file_paths: List[str], archive_name: str) -> str:
        """
        Create a ZIP archive containing multiple filled forms
        
        Args:
            file_paths: List of file paths to include in archive
            archive_name: Name for the ZIP archive
            
        Returns:
            Path to created ZIP archive
        """
        try:
            import zipfile
            
            zip_path = os.path.join(self.output_dir, f"{archive_name}.zip")
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file_path in file_paths:
                    if os.path.exists(file_path):
                        zipf.write(file_path, os.path.basename(file_path))
            
            logger.info(f"Created ZIP archive: {zip_path}")
            return zip_path
            
        except Exception as e:
            logger.error(f"Error creating ZIP archive: {str(e)}")
            return ""

# Example usage and testing
if __name__ == "__main__":
    # Test the coordinator
    try:
        # Initialize coordinator (make sure OPENAI_API_KEY is set in environment)
        coordinator = OpenAIAgentCoordinator()
        
        # Test with sample files
        test_documents = ["sample_document.pdf"]  # Replace with actual document paths
        test_forms = ["sample_form.pdf"]  # Replace with actual form paths
        
        # Check if test files exist
        documents_exist = all(os.path.exists(doc) for doc in test_documents)
        forms_exist = all(os.path.exists(form) for form in test_forms)
        
        if documents_exist and forms_exist:
            print("🚀 Testing complete two-agent workflow...")
            
            # Run complete workflow
            result = coordinator.extract_and_fill_workflow(test_documents, test_forms)
            
            if result["success"]:
                print("✅ Two-agent workflow completed successfully!")
                print(f"📊 Workflow Summary:")
                summary = result["workflow_summary"]
                print(f"  Documents processed: {summary['total_documents_processed']}")
                print(f"  Forms filled: {summary['successful_form_fills']}/{summary['total_forms_processed']}")
                print(f"  Duration: {summary['workflow_duration_seconds']:.2f} seconds")
                print(f"  Extraction data: {summary['extraction_data_file']}")
                print(f"  Filled forms: {len(summary['filled_form_paths'])}")
                print(f"  Report saved: {result['workflow_report_path']}")
            else:
                print(f"❌ Workflow failed: {result['error']}")
                print(f"Failed at stage: {result.get('stage', 'unknown')}")
        else:
            print("Test files not found. Testing individual components...")
            
            # Test extraction only
            if documents_exist:
                print("🔍 Testing extraction agent...")
                extraction_result = coordinator.extract_data_only(test_documents)
                if extraction_result["success"]:
                    print("✅ Extraction test successful!")
                else:
                    print(f"❌ Extraction test failed: {extraction_result['error']}")
            
            print("\nTo test the complete workflow, provide:")
            print(f"  Documents: {test_documents}")
            print(f"  Forms: {test_forms}")
            
    except Exception as e:
        print(f"❌ Error testing coordinator: {str(e)}")
        print("Make sure to set the OPENAI_API_KEY environment variable.")
