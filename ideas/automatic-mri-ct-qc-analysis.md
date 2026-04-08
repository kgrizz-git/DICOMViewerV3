# Automatic MRI and CT Quality Control Analysis

## Concept Overview
An automated system for quality control (QC) analysis of MRI and CT imaging data that integrates with existing workflows, leveraging DICOM metadata and image analysis techniques to ensure equipment performance and image quality standards are maintained.

## Core Features

### Automatic Image Analysis
- **Automated QC Metrics**: Calculate SNR, uniformity, geometric accuracy, resolution, low contrast detectability
- **Phantom Detection**: Automatically identify and analyze QC phantom images
- **Trend Analysis**: Track performance metrics over time to detect gradual degradation
- **Alert System**: Notify when metrics fall outside acceptable ranges
- **Multi-Modality Support**: Handle both MRI and CT QC protocols
- **ACR QC Tests**: Complete ACR phantom protocol including slice thickness, spatial resolution, low contrast detectability, and CT number accuracy

### MRI Laser Alignment QC Check
- **Table Position Verification**: Monitor that the table has not moved between scans
- **Z-Plane Prescription Validation**: Ensure z-plane prescription remains consistent from initial 3-plane localizer
- **DICOM Tag Analysis**: 
  - Table Position (0018,9327) or Table Longitudinal Position (0018,9306)
  - Frame of Reference UID (0020,0052)
  - Image Position Patient (0020,0032)
  - Image Orientation Patient (0020,0037)
- **Automated Comparison**: Compare localizer to subsequent imaging sequences
- **Tolerance Checking**: Flag deviations beyond acceptable thresholds

## Available Libraries and Packages

### Core Python Libraries
- **pydicom**: DICOM file reading, manipulation, and metadata extraction - essential foundation for all DICOM-based QC workflows
- **SimpleITK** / **ITK**: Medical image processing and analysis
- **scikit-image**: Image processing algorithms for QC metrics
- **numpy** / **scipy**: Numerical computations and signal processing
- **matplotlib** / **plotly**: Visualization and reporting
- **pynetdicom**: DICOM networking for PACS integration

### Specialized QC Analysis Packages
- **pylinac**: Comprehensive radiotherapy QC package supporting multiple phantom types (Catphan, Leeds, ACR CT/MRI phantoms). Provides automated analysis for:
  - CT number accuracy and uniformity
  - Spatial resolution (MTF)
  - Low contrast detectability
  - Slice thickness and geometric accuracy
  - Noise and artifact analysis
- **hazen**: Medical physics QC analysis library with modules for MRI and CT, focused on automated ACR phantom analysis
- **MRQy**: MRI quality metrics extraction tool for research and clinical QC
- **ACRToolkit**: ACR phantom analysis tools

### Image Analysis Tools
- **dcmtk**: DICOM toolkit for file operations and networking
- **dcm4che**: Java-based DICOM toolkit
- **OHIF Viewer**: Open-source web-based DICOM viewer with extensibility
- **cornerstone.js**: JavaScript DICOM image rendering library

### QC-Specific Resources
- **QATrack+**: Web-based QA/QC tracking system for radiation oncology and medical imaging
- **CT QC phantoms**: Catphan (CBCT/CT QC), ACR CT phantom, Gammex phantoms
- **MRI QC phantoms**: ACR MRI phantom, ADNI phantom, NIST/ISMRM phantom
- **ImageJ/FIJI**: Extensible image analysis platform with scripting and QC plugins
- **QuickCheck**: Commercial automated QC software for CT/MRI
- **Radformation AutoContour/ClearCheck**: AI-powered QC tools

## Going Beyond Existing Tools

### Why Build Custom Analysis Tools

While packages like **pylinac**, **hazen**, and **MRQy** provide excellent starting points, there are compelling reasons to develop custom analysis capabilities:

1. **Specific ACR Tests Not Fully Automated**
   - Low contrast detectability scoring (subjective human component)
   - Automated artifact classification beyond basic detection
   - Multi-vendor phantom adaptation
   - Custom institutional protocols and acceptance criteria

2. **Extended Analysis Capabilities**
   - Low contrast detectability with AI-assisted scoring
   - Advanced noise texture analysis
   - Temporal stability metrics across multiple acquisitions
   - Cross-modality QC correlation (e.g., CT vs. MRI geometric accuracy)
   - Institution-specific phantom designs and protocols

3. **Integration and Workflow Needs**
   - Seamless PACS integration with custom routing logic
   - Real-time analysis during acquisition
   - Custom reporting formats for regulatory compliance
   - Multi-site harmonization with vendor-agnostic metrics

4. **Novel QC Approaches**
   - Machine learning for predictive maintenance
   - Deep learning artifact detection and classification
   - Statistical process control with custom control charts
   - Radiomics-based QC feature extraction

### Recommended Hybrid Approach

**Leverage Existing Tools:**
- Use **pylinac** for standard Catphan and ACR phantom analysis
- Use **pydicom** for all DICOM parsing and metadata extraction
- Use **hazen** modules for vendor-specific ACR protocols
- Utilize **scikit-image** and **scipy** for core image processing

**Build Custom Extensions:**
- **Enhanced Low Contrast Detectability**: Implement AI-assisted scoring that combines traditional methods with deep learning to improve objectivity and reproducibility
- **Missing ACR Tests**: Automate tests not covered by existing packages (e.g., specific MRI uniformity scoring, artifact classification)
- **Vendor Harmonization**: Create vendor-agnostic analysis pipelines that normalize results across different scanner manufacturers
- **Advanced Trending**: Statistical process control dashboards with predictive analytics
- **Custom Phantoms**: Support for institution-specific or research phantoms not in standard packages

### Advanced Analytics
- **Machine Learning Integration**: Train models to detect subtle QC failures or predict equipment issues
- **Deep Learning for Artifact Detection**: Automatically identify and classify image artifacts
- **Statistical Process Control**: Apply industrial QC methods to medical imaging
- **Predictive Maintenance**: Use QC trends to predict equipment failures before they occur
- **Multi-Site Comparison**: Harmonize and compare QC across multiple scanners/facilities

### Enhanced Automation
- **Natural Language Processing**: Parse radiology reports for incidental QC issues
- **Automated Protocol Verification**: Check that scan protocols match standards
- **Smart Scheduling**: Automatically schedule QC scans based on usage patterns
- **Cross-Reference with Service Records**: Correlate QC results with maintenance history

## ACR QC Tests and Implementation

### ACR CT Phantom Tests (Comprehensive Coverage)

1. **CT Number Accuracy**
   - Water ROI measurement (should be 0 ± 5 HU)
   - Material inserts (bone, acrylic, polyethylene, air)
   - Implementation: Available in pylinac, can extend for custom tolerances

2. **Low Contrast Detectability** ⭐ **Priority for Custom Development**
   - Detect smallest visible target in low contrast module
   - Standard: 6mm diameter at 0.3% contrast (3 HU @ 120 kVp)
   - Challenges: 
     - Subjective visual assessment difficult to automate
     - Variable observer performance
     - Noise-dependent visibility
   - Custom Solution Approach:
     - CNN-based target detection trained on radiologist scoring
     - Rose model calculations for theoretical detectability
     - Contrast-to-noise ratio (CNR) measurements
     - Automated scoring with confidence intervals
     - Human-in-the-loop validation for borderline cases

3. **Spatial Resolution (High Contrast)**
   - Line pair gauge measurements
   - MTF (Modulation Transfer Function) analysis
   - Implementation: pylinac provides MTF, custom extensions for specific gauges

4. **Uniformity**
   - Center vs. peripheral ROI measurements
   - Standard: ±5 HU across phantom
   - Implementation: Available in multiple packages, easy to customize

5. **Slice Thickness Accuracy**
   - Ramp phantom analysis
   - FWHM measurements
   - Implementation: Requires custom development for specific ramps

6. **Noise**
   - Standard deviation in uniform region
   - Implementation: Straightforward with numpy/scipy

### ACR MRI Phantom Tests (Comprehensive Coverage)

1. **Geometric Accuracy**
   - Distance measurements in multiple directions
   - Standard: ±2mm tolerance
   - Implementation: Basic in existing tools, custom for multi-vendor

2. **High Contrast Spatial Resolution**
   - Array of holes/points at variable spacing
   - Standard: Resolve 1.0mm holes
   - Implementation: Pattern detection algorithms, custom development needed

3. **Slice Thickness Accuracy**
   - Crossed-wedge or ramp method
   - Standard: ±5mm or ±30% of prescribed
   - Implementation: Custom algorithm required

4. **Slice Position Accuracy**
   - Bar pattern at known positions
   - Standard: ±5mm
   - Implementation: Custom development

5. **Image Intensity Uniformity**
   - PIU (Percent Integral Uniformity) calculation
   - Standard: >87.5% for 3T, >82% for 1.5T
   - Implementation: MRQy provides this, can extend

6. **Percent Signal Ghosting**
   - Ratio of ghost to signal intensity
   - Standard: <2.5%
   - Implementation: Requires ROI placement automation

7. **Low Contrast Object Detectability** ⭐ **Priority for Custom Development**
   - Spokes pattern with varying contrast
   - Standard: Visualize 9, 10, 11mm spokes in contrast detail array
   - Similar challenges to CT low contrast:
     - Subjective assessment
     - Observer variability
   - Custom Solution Approach:
     - Automated spoke detection using edge detection and pattern matching
     - CNR measurements for each spoke position
     - Machine learning classification trained on expert scoring
     - Standardized viewing conditions in automated pipeline

### Missing Tests Requiring Custom Development

1. **Artifact Assessment** (Beyond Basic Detection)
   - Motion artifacts
   - Aliasing/wraparound
   - Metal artifacts
   - Chemical shift artifacts
   - Zipper artifacts
   - Ghosting patterns
   - Custom ML-based artifact classifier

2. **Advanced Noise Analysis**
   - Noise texture analysis
   - Noise power spectrum (NPS)
   - Correlated vs. uncorrelated noise
   - Temporal stability of noise characteristics

3. **Dynamic Range Testing**
   - Linearity across full signal range
   - Sensitivity to low signal levels
   - Saturation characteristics

4. **Patient-Specific QC**
   - In-vivo QC metrics from clinical scans
   - Background monitoring without dedicated phantoms
   - Continuous quality monitoring

5. **Multi-Modality Registration Accuracy**
   - CT-MRI fusion accuracy
   - PET-CT alignment verification
   - Reference phantom for cross-modality validation

### Enhanced Automation

## Integration Approaches

### DICOM Viewer Integration
- **Plugin Architecture**: Develop plugins for existing viewers (3D Slicer, Horos, OHIF)
- **One-Click Analysis**: Right-click on QC image series → "Run QC Analysis"
- **In-Viewer Results**: Display results directly in the viewer interface
- **Embedded Reporting**: Generate QC reports within the viewing workflow
- **Real-Time Feedback**: Immediate analysis results as images are reviewed

### Automatic Pipeline Implementation

#### Server-Based Processing
- **DICOM Listener**: Set up DICOM C-STORE SCP to receive images
- **Routing Logic**: Automatically identify QC studies by:
  - Study/Series Description
  - Protocol Name
  - Patient ID patterns (e.g., phantom IDs)
  - Scheduled Procedure Step ID
- **Processing Queue**: Manage analysis jobs with priority levels
- **Result Storage**: Store results in PACS or dedicated QC database

#### Folder Monitoring Approach
- **File System Watcher**: Monitor designated folders for new DICOM files
- **Hot Folder Processing**: Automatically process images placed in specific directories
- **Network Share Integration**: Watch network shares for multi-site deployments
- **Batch Processing**: Handle bulk analysis of historical QC data

#### Hybrid Workflow
- **PACS Integration**: Query/retrieve QC studies from PACS using DICOM Q/R
- **HL7 Integration**: Trigger analysis based on HL7 procedure completion messages
- **RESTful API**: Provide web API for flexible integration options
- **Cloud Processing**: Upload to cloud for analysis, download results

## Technical Architecture

### Core Components

1. **DICOM Interface Layer**
   - DICOM network services (C-STORE, C-FIND, C-MOVE)
   - File system monitoring
   - DICOM tag extraction and parsing
   - Series/Study organization

2. **Image Processing Engine**
   - Phantom detection and registration
   - ROI analysis and metric calculation
   - Geometric accuracy measurements
   - Signal and noise quantification
   - **pylinac integration** for standard phantom analysis
   - **Custom modules** for low contrast detectability
   - **Extended ACR test modules** not in existing packages

3. **Laser Alignment Checker**
   - DICOM tag extraction module
   - Coordinate transformation calculations
   - Position comparison algorithms
   - Tolerance checking and reporting

4. **Database and Reporting**
   - QC metrics storage (SQL/NoSQL)
   - Trend analysis and visualization
   - PDF report generation
   - Alert and notification system

5. **Integration Layer**
   - Viewer plugin interfaces
   - RESTful API endpoints
   - HL7/FHIR messaging
   - Email/SMS notifications

### Custom Tool Development Priorities

1. **Low Contrast Detectability AI Engine**
   - Training dataset: Expert-scored phantom images
   - CNN architecture for target detection
   - Confidence scoring for automated vs. manual review
   - Integration with pylinac for complementary metrics
   - Validation against human observers

2. **Enhanced ACR Test Suite**
   - Automated slice thickness/position for MRI
   - Percent signal ghosting with ROI automation
   - High contrast resolution pattern detection
   - Vendor-agnostic normalization
   - Extended beyond standard pylinac capabilities

3. **Artifact Classification System**
   - Multi-class artifact detector (motion, metal, aliasing, etc.)
   - Severity scoring (mild/moderate/severe)
   - Spatial localization of artifacts
   - Temporal tracking of artifact patterns
   - Correlation with scanner maintenance

4. **Advanced Statistical Process Control**
   - Control charts with automated rule detection
   - Multivariate analysis of correlated QC metrics
   - Predictive analytics for performance degradation
   - Alert system with customizable thresholds
   - Cross-scanner/site comparison dashboards

5. **Integration Wrapper for Multiple Tools**
   - Unified interface combining pylinac, hazen, MRQy
   - Orchestration layer for workflow automation
   - Result harmonization across different analysis packages
   - Consistent reporting format
   - Error handling and fallback mechanisms

### Data Flow

1. Image Acquisition → DICOM send or file save
2. Automatic Detection → Identify as QC study
3. Preprocessing → Extract metadata, organize series
4. Analysis → Run appropriate QC algorithms
5. Comparison → Check against baselines and tolerances
6. Reporting → Generate reports and alerts
7. Storage → Archive results and trends

## Implementation Strategy

### Phase 1: Core QC Analysis (MVP)
- Integrate **pydicom** for DICOM file reading and metadata extraction
- Leverage **pylinac** for standard Catphan/ACR phantom analysis
- Implement basic phantom detection using scikit-image
- Standard QC metric calculations (uniformity, SNR, noise)
- Manual trigger via command line
- Basic reporting to CSV/JSON with trend data
- Validation against manual measurements

### Phase 2: Custom Analysis Extensions
- **Low Contrast Detectability Module**:
  - Implement automated target detection algorithms
  - Develop CNN-based scoring model
  - Create CNR measurement tools
  - Build human-in-the-loop validation interface
- **Missing ACR Tests Implementation**:
  - Slice thickness accuracy (ramp method)
  - Slice position accuracy
  - Percent signal ghosting (MRI)
  - High contrast spatial resolution enhancements
- **Artifact Detection and Classification**:
  - Build ML-based artifact classifier
  - Create artifact severity scoring
  - Implement automated artifact reporting
- Database integration for historical trending
- Basic web dashboard for results visualization

### Phase 3: Automation and Integration
- DICOM listener implementation (pynetdicom)
- Folder monitoring for hot-folder workflows
- Automatic study detection and routing
- PACS integration for Q/R operations
- Advanced web dashboard with statistical process control
- Multi-site support and data aggregation
- Laser alignment checker module

### Phase 4: Advanced Analytics
- Machine learning integration for predictive maintenance
- Deep learning models for enhanced image quality assessment
- Statistical process control charts and alerts
- Cross-modality QC harmonization
- Natural language report generation
- Integration with service records and maintenance logs

### Phase 5: Production Deployment
- Robust error handling
- Security and access control
- Performance optimization
- Comprehensive documentation
- Validation and regulatory compliance

## Laser Alignment QC Implementation Details

### Algorithm Overview
```
1. Identify 3-plane localizer (axial, sagittal, coronal)
2. Extract DICOM tags from localizer images:
   - Frame of Reference UID
   - Image Position Patient
   - Table Position
3. For subsequent sequences in the exam:
   - Extract same DICOM tags
   - Compare Frame of Reference UID (must match)
   - Calculate position differences
   - Check if table position changed
   - Verify z-plane prescription consistency
4. Flag if:
   - Table position differs by > tolerance (e.g., 1mm)
   - Image position differs unexpectedly
   - Frame of Reference UID doesn't match
```

### Key DICOM Tags
- **Table Position (0018,9327)**: Patient table longitudinal position
- **Frame of Reference UID (0020,0052)**: Links images in same coordinate system
- **Image Position Patient (0020,0032)**: X, Y, Z coordinates of upper left pixel
- **Image Orientation Patient (0020,0037)**: Direction cosines
- **Slice Location (0020,1041)**: Relative position of image plane
- **Patient Position (0018,5100)**: Patient orientation (HFS, FFS, etc.)

### Tolerance Definitions
- Table position: ±1-2mm
- Image position: ±1mm
- Slice prescription: ±1mm or ±5% of FOV
- Angular alignment: ±2 degrees

## Applications and Use Cases

### Clinical QC
- Daily ACR phantom scans
- Weekly/monthly preventive maintenance QC
- Post-service verification
- Accreditation compliance (ACR, Joint Commission)

### Research Imaging
- Multi-site clinical trial harmonization
- Longitudinal study quality monitoring
- Protocol compliance verification
- Scanner upgrade validation

### Quality Improvement
- Performance trending across fleet
- Vendor comparison analysis
- Protocol optimization
- Technologist training feedback

## Technical Challenges

### Image Processing
- Robust phantom detection in variable positioning
- Handling different phantom types and manufacturers
- Dealing with artifacts and image quality issues
- Computational efficiency for large studies

### DICOM Complexity
- Tag variations across vendors
- Private tag handling
- Enhanced DICOM (multi-frame images)
- Compressed transfer syntaxes

### Integration
- PACS vendor compatibility
- Viewer plugin architecture differences
- Network security and firewall issues
- Authentication and authorization

### Validation
- Establishing ground truth for QC metrics
- Regulatory compliance for automated QC
- Clinical acceptance and trust
- Integration with existing workflows

## Next Steps

1. **Requirement Gathering**
   - Survey potential users (physicists, QC coordinators)
   - Define priority features
   - Establish acceptance criteria
   - Review regulatory requirements

2. **Prototype Development**
   - Implement basic DICOM reading
   - Develop core QC metrics
   - Create simple laser alignment checker
   - Test with real QC data

3. **Pilot Testing**
   - Deploy at single site
   - Gather user feedback
   - Validate against manual QC
   - Refine algorithms

4. **Production Development**
   - Scale to multiple sites
   - Implement full automation
   - Develop viewer integrations
   - Create comprehensive documentation

## Resources and References

### Standards and Guidelines
- ACR MRI Quality Control Manual
- ACR CT Quality Control Manual
- AAPM Reports on QC (TG-142, TG-66, etc.)
- DICOM Standard (especially Part 3: Information Object Definitions)
- NEMA Standards for phantom specifications
- IEC Standards for image quality (IEC 61223)

### Open Source Projects and Packages
- **pylinac**: https://github.com/jrkerns/pylinac - Comprehensive radiotherapy/diagnostic QC
- **pydicom**: https://github.com/pydicom/pydicom - DICOM file handling in Python
- **hazen**: https://github.com/GSTT-CSC/hazen - Medical physics QC library
- **MRQy**: https://github.com/ccipd/MRQy - MRI quality metrics
- **QATrack+**: https://github.com/qatrackplus/qatrackplus - Web-based QA/QC tracking
- **dcmtk**: https://dicom.offis.de/dcmtk - C++ DICOM toolkit
- **3D Slicer**: https://www.slicer.org/ - Medical image analysis platform
- **ITK-SNAP**: http://www.itksnap.org/ - Segmentation and image analysis
- **scikit-image**: https://scikit-image.org/ - Image processing in Python

### Commercial Solutions
- GE QC tools
- Siemens syngo QC
- Philips QC applications
- Third-party QC software (ACRToolkit, etc.)

### Academic Literature
- Papers on automated QC methods
- Machine learning for artifact detection
- Statistical process control in imaging
- Multi-site harmonization studies
- Low contrast detectability assessment methodologies
- CNN-based medical image quality assessment
- Rose model and observer performance studies
- Radiomics quality control approaches

### Key Research Papers
- "Automated Quality Control in Image Segmentation" - ML approaches to QC
- "Low-Contrast Detectability in CT: Effects of Radiation Dose" - LC detectability fundamentals
- "Deep Learning for Medical Image Quality Assessment" - DL QC methods
- "Statistical Process Control for Medical Imaging QC" - SPC applications
- "Harmonization of Multi-Site Imaging Data" - Multi-center QC strategies
