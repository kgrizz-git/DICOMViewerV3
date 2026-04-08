# Peak Skin Dose Calculator

Create a program to calculate peak skin dose from radiation dose structured reports (RDSR) in fluoroscopy procedures.

**Platform**: Cross-platform (MATLAB initially, potentially port to other languages)

**Concept**: Develop a tool that processes RDSR data to calculate and visualize peak skin dose distribution for fluoroscopy procedures, helping assess radiation exposure risks.

**Technical Approach**:
- Parse RDSR XML/JSON data from fluoroscopy systems
- Extract dose parameters (DAP, exposure time, beam geometry)
- Implement skin dose calculation algorithms
- Generate dose distribution maps
- Provide visualization and reporting

**Available Resources**:
- Existing MATLAB code to start from
- RDSR data format specifications
- Medical physics dose calculation methodologies

**Potential Implementation**:
- MATLAB GUI for data import and processing
- Dose calculation engine based on established protocols
- 2D/3D visualization of skin dose distribution
- Export capabilities for reports and documentation
- Validation against reference measurements

**Key Features**:
- Support for multiple fluoroscopy vendors
- Real-time dose tracking during procedures
- Threshold alerts for high-dose areas
- Historical dose tracking and trending
- Compliance with radiation safety standards

**Applications**:
- Interventional radiology dose monitoring
- Cardiology procedure safety
- Radiation safety officer tools
- Patient dose documentation
- Quality improvement initiatives
