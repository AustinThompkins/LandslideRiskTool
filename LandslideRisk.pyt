# -*- coding: utf-8 -*-

import arcpy
from arcpy.sa import *
from arcpy.ia import *

class Toolbox:
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Landslide Risk Assessment Tool"
        self.alias = "LandslideRisk"
        self.tools = [LandslideRiskTool]


class LandslideRiskTool:
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Landslide Risk Assessment Tool"
        self.description = "Assess landslide risk based on a elevation and rainfall data."

    def getParameterInfo(self):
        """Define the tool parameters."""
        param0 = arcpy.Parameter( displayName="DEM Raster (m)", name="dem_raster", datatype="DERasterDataset", parameterType="Required", direction="Input")
        
        param1 = arcpy.Parameter(displayName="Rainfall Raster (mm)", name="rainfall_raster", datatype="DERasterDataset", parameterType="Required",direction="Input")
        
        param2 = arcpy.Parameter(displayName="Study Area", name="study_area", datatype="DEShapeFile", parameterType="Required", direction="Input")
            
        param3 = arcpy.Parameter(displayName="Point of Interest's Longitude (x-coordinate)", name="x_coordinates", datatype="GPString", parameterType="Optional", direction="Input")
        
        param4 = arcpy.Parameter(displayName="Point of Interest's Latitude (y-coordinate)", name="y_coordinates", datatype="GPString", parameterType="Optional", direction="Input")
        
        param5 = arcpy.Parameter(displayName="Select Folder Location to Store Outputs", name="output_location", datatype="DEWorkspace", parameterType="Required", direction="Input")
                
        params = [param0, param1, param2, param3, param4, param5]
        return params

    def isLicensed(self):
        """Set whether the tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed. This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter. This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        dem_raster = parameters[0].valueAsText
        rfall_raster = parameters[1].valueAsText
        study_area = parameters[2].valueAsText
        x_coordinate = parameters[3].valueAsText
        y_coordinate = parameters[4].valueAsText 
        output_location = parameters[5].valueAsText
        
        arcpy.AddMessage("Parameters Loaded In.")
        
        arcpy.env.cellSize = rfall_raster
        arcpy.env.extent = rfall_raster
        arcpy.env.mask = rfall_raster
        arcpy.env.snapRaster = rfall_raster
   
        # Check if DEM and rainfall datasets have the same spatial resolution
        dem_details = arcpy.Describe(dem_raster)
        rainfall_details = arcpy.Describe(rfall_raster)

        if dem_details.meanCellHeight != rainfall_details.meanCellHeight or dem_details.meanCellWidth != rainfall_details.meanCellWidth:
            arcpy.AddMessage("The DEM and rainfall datasets have different spatial resolutions. They will be resampled.")
            
            # Determine the lower resolution (larger cell sizes) 
            target_resolution = max(dem_details.meanCellHeight, dem_details.meanCellWidth, rainfall_details.meanCellHeight, rainfall_details.meanCellWidth)

            # Resample DEM
            if dem_details.meanCellHeight != target_resolution or dem_details.meanCellWidth != target_resolution:
                dem_raster = Resample(dem_raster, target_resolution)

            # Resample rainfall
            if rainfall_details.meanCellHeight != target_resolution or rainfall_details.meanCellWidth != target_resolution:
                rfall_raster = Resample(rfall_raster, target_resolution)
        
        arcpy.AddMessage("Spatial Resolution Check Passed.")

        # Check if datasets have the same coordinate reference system
        if dem_details.spatialReference.exportToString() != rainfall_details.spatialReference.exportToString(): 
            arcpy.AddMessage("The DEM and rainfall datasets have different coordinate reference systems.")
            
        arcpy.AddMessage("CRS Check Passed.")
                
        # Clip DEM and rainfall datasets to the study area shapefile
        dem_clipped_path = output_location + "\\dem_clip.tif"
        arcpy.Clip_management(dem_raster, "#", dem_clipped_path, study_area) 
        
        rfall_c_path = output_location + "\\rfall_clip.tif"
        arcpy.Clip_management(rfall_raster, "#", rfall_c_path, study_area)
        
        # Load clip results into script 
        dem_clipped = arcpy.Raster(dem_clipped_path)
        rfall_clipped = arcpy.Raster(rfall_c_path)
        
        arcpy.AddMessage("Clips Passed.")
        
        # Calculate Slope from the DEM
        slope = SurfaceParameters(dem_clipped, "SLOPE")
        
        arcpy.AddMessage("Slope Calculation Passed.")
        
        # Reclassify slope data
        slope_reclassified = Reclassify(slope, "Value", RemapRange([[0, 15, 1], [15, 25, 2], [25, 30, 3], [35, 45, 4], [45, 90, 5]]))

        # Reclassify rainfall data
        rainfall_reclassified = Reclassify(rfall_clipped, "Value", RemapRange([[0, 75, 1], [75, 150, 2], [150, 225, 3], [225, 300, 4], [300, 10000, 5]]))
        
        # Reclassify elevation data
        elevation_reclassified = Reclassify(dem_clipped, 'Value', RemapRange([[-500, 500, 1], [500, 1000, 2], [1000, 1500, 3], [1500, 2000, 4], [2000, 11000, 5]]))
        
        arcpy.AddMessage("Reclassifications Passed.")

        # Risk Calculation
        risk = slope_reclassified * 0.5 + rainfall_reclassified * 0.3 + elevation_reclassified * 0.2 
        
        arcpy.AddMessage("Risk Calculation Passed.")
        
        # Define the reclassification ranges for risk categories
        risk_ranges = [[0, 1, "Low Risk"], [1, 3, "Moderate Risk"], [3, 5, "High Risk"]]
        
        # Output Risk raster
        output_risk_raster = output_location + "\\landslide_risk_result_2.tif"
        risk.save(output_risk_raster)
    
        # Add Risk raster to the map
        # arcpy.management.MakeRasterLayer(output_risk_raster, "landslide_risk_result")
        # arcpy.management.AddLayer("CURRENT", "landslide_risk_result", "TOP")
        
        # Check if the user provided coordinates 
        if len(x_coordinate) > 0 and len(y_coordinate) > 0:
            
            # Check if the coordinates are inside the study area
            user_point = arcpy.PointGeometry(arcpy.Point(x_coordinate, y_coordinate))

            if not user_point.overlaps(dem_clipped):
                arcpy.AddMessage("The coordinates you have input are not inside the provided study area.")
            
            else: 
                point_risk_value = arcpy.management.GetCellValue(risk, user_point)
                
                arcpy.AddMessage("Point risk level is being assessed...")
                
                # Assign a risk level to the risk value at the coorindates
                for range in risk_ranges:
                    if point_risk_value >= range[0] and point_risk_value < range[1]: # Checks if the risk value at the point is > the min or < the max for each risk level range
                        risk_level = range[2] # Corresponds with "Low Risk" etc. in the risk categories 
                        arcpy.AddMessage(f"The landslide risk level at the provided coordinates is: {risk_level}")
                        return

        arcpy.AddMessage("The landslide risk assessment ran successfully!")
        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
