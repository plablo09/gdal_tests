import ogr
import osr
import gdal
import os
from gdalconst import *

dataset = gdal.Open("data/ortofoto_e14s427q41.img", GA_ReadOnly)
input_projection = dataset.GetProjectionRef()
spatial_reference = osr.SpatialReference()
spatial_reference.ImportFromWkt(input_projection)

proj_srid = spatial_reference.GetAttrValue("AUTHORITY",1)
print proj_srid
geoTransform=dataset.GetGeoTransform(can_return_null = True)
points = [(0.0,0.0),(0.0,dataset.RasterYSize),(dataset.RasterXSize,dataset.RasterYSize),(dataset.RasterXSize,0.0)]
print str(points)
geoPoints=[(geoTransform[0]+geoTransform[1]*p[0] + geoTransform[2]*p[1], geoTransform[3]+geoTransform[4]*p[0]+geoTransform[5]*p[1]) for p in points]
print str(geoPoints)

ring = ogr.Geometry(ogr.wkbLinearRing)
ring.SetCoordinateDimension(2)
ring.AddPoint_2D(geoPoints[0][0],geoPoints[0][1])
ring.AddPoint_2D(geoPoints[1][0],geoPoints[1][1])
ring.AddPoint_2D(geoPoints[2][0],geoPoints[2][1])
ring.AddPoint_2D(geoPoints[3][0],geoPoints[3][1])
ring.AddPoint_2D(geoPoints[0][0],geoPoints[0][1])

outSpatialRef = osr.SpatialReference()
outSpatialRef.ImportFromEPSG(4326)

if proj_srid != 4326:
    coordTrans = osr.CoordinateTransformation(spatial_reference, outSpatialRef)
    ring.Transform(coordTrans)
    bbox=[]
    for p in range(0,len(ring.GetPoints())-1):
       point = ogr.Geometry(ogr.wkbPoint)
       point.AddPoint_2D(ring.GetPoints()[p][0],ring.GetPoints()[p][1])
       bbox.append(point)


#
poly = ogr.Geometry(ogr.wkbPolygon)
poly.AddGeometry(ring)
#archivo de salida
outShapefile = "data/raster_extent.shp"
outDriver = ogr.GetDriverByName("ESRI Shapefile")
# Remove output shapefile if it already exists
if os.path.exists(outShapefile):
    outDriver.DeleteDataSource(outShapefile)

# Create the output shapefile
outDataSource = outDriver.CreateDataSource(outShapefile)
outLayer = outDataSource.CreateLayer("raster_extent", geom_type=ogr.wkbPolygon)

# Add an ID field
idField = ogr.FieldDefn("id", ogr.OFTInteger)
outLayer.CreateField(idField)

# Create the feature and set values
featureDefn = outLayer.GetLayerDefn()
feature = ogr.Feature(featureDefn)
feature.SetGeometry(poly)
feature.SetField("id", 1)
outLayer.CreateFeature(feature)

#Close DataSource
#dataset.Destroy()
outDataSource.Destroy()
