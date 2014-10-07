# -*- coding: utf-8 -*-
import sys
import osr
import ogr
import gdal
from shapely.wkt import loads
import logging

log = logging.getLogger(__name__)

class InvalidFormatError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class InvalidConnection(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class InvalidPostgisLayer(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def pretify_wkt(str):
    """Regresa una lista con los renglones indentados para presentar el wkt como leible para humano."""
    lista = str.split(',')
    renglones=[]
    ident = 0;
    for i,el in enumerate(lista):
       abren = el.count('[')
       cierran = el.count(']')
       ident += abren - cierran
       espacios = '';
       for x in range(1,ident):
        espacios +='  '
       if el.startswith('PROJCS'):
           renglones.append(espacios + el + ',')
       if el.startswith('GEOGCS'):
           renglones.append(espacios + el + ',')
       if el.startswith('DATUM'):
           renglones.append(espacios + el + ',')
       if el.startswith('SPHEROID'):
           renglones.append(espacios + el + ',' + lista[i+1] + ',' + lista[i+2] +',')
       if el.startswith('AUTHORITY'):
           renglones.append(espacios + el + ',' + lista[i+1] + ',' )
       if el.startswith('PRIMEM'):
           renglones.append(espacios + el + ',' + lista[i+1] + ',' )
       if el.startswith('UNIT'):
           renglones.append(espacios + el + ',' + lista[i+1] + ',' )
       if el.startswith('PROJECTION'):
           renglones.append(espacios + el + ',')
       if el.startswith('PARAMETER'):
           renglones.append(espacios + el +','+ lista[i+1]+',')
       if el.startswith('AXIS'):
           renglones.append(espacios + el +','+ lista[i+1]+',')
       if el.startswith('VERT_CS'):
           renglones.append(espacios + el + ',')
       if el.startswith('VERT_DATUM'):
           renglones.append(espacios + el + ',')
       if el.startswith('COMPD_CS'):
           renglones.append(espacios + el + ',')
       if el.startswith('TOWGS84'):
           renglones.append(espacios + el + ',')
       if el.startswith('FITTED_CS'):
           renglones.append(espacios + el + ',')
       if el.startswith('LOCAL_CS'):
           renglones.append(espacios + el + ',')
       if el.startswith('LOCAL_DATUM'):
           renglones.append(espacios + el + ',')

    return renglones


class VectorDataSource():
    """Crea una capa vectorial a partir de un shapefile o una conexión a PostGis.

    Attributes:
        capa (ogr Layer) la capa

    Args:
        shp_path (str,optional) el path (absoluto) a los archivos del shape.
        postgis_conn (dict, optional) diccionario con la información de conección {usuario_bd:usuario en la bd,password_bd:el password,
                                                                                    url:el url del servidor,tabla:la tabla en la bd,
                                                                                    bd:el nombre de la base de datos}
        type (str,optional) 'map_index' para indicar que la capa corresponde al mapa índice de un raster_package

     """

    def __init__(self,shp_path=None,postgis_conn=None,type=None):
        self.capa = None
        self.shp_path=shp_path
        self.postgis_conn = postgis_conn
        self.type = type
        if type is not None:
            self.type = type

    def readMetadata(self):
        """Regresa un diccionario con la información leida de la fuente de datos.

        vector_info['feature_count'] --> La cantidad de features.
        vector_info['prj_info'] --> (epsg code,pretty wkt) Información de la proyeccion.
        vector_info['prj_dict'] --> diccionario con la información de proyección organizada para meterla en el iso_xml
        vector_info['field_count'] --> número de campos.
        vector_info['att_info'] --> Diccionario. Para cada nombre de atributo: Diccionario {'tipo':f_type,'descripcion':''}.
        vector_info['bbox'] --> Lista con las coordenadas del extent (xmin,ymax,xmax,ymin).
        vector_info['bbox_wkt'] --> el wkt del polígono nque representa la extensión de la capa
        """
        if self.shp_path is not None:
            driver = ogr.GetDriverByName('ESRI Shapefile')
            shape = driver.Open(self.shp_path,0)
            if shape is not None:
                self.capa=shape.GetLayer()
            else:
                raise InvalidFormatError('No se pudo leer el archivo')

        if self.postgis_conn is not None:
            connString = "PG: host="+self.postgis_conn['url']+ " dbname=" + self.postgis_conn['bd'] + " user=" + \
                             self.postgis_conn['usuario_bd'] + " password=" + self.postgis_conn['password_bd']
            try:
                conn = ogr.Open(connString)
            except:
                raise InvalidConnection('No se pudo conectar a la base de datos, verifica los parámetros del servidor o checa que éste esté configurado para aceptar conecciones')

            try:
                self.capa= conn.GetLayer(self.postgis_conn['tabla'].encode('ascii','ignore'))
            except:
               raise InvalidPostgisLayer('La tabla no existe en la base de datos o el usuario no tiene permisos suficientes')

        if self.capa is None:
            raise InvalidPostgisLayer('La tabla no existe en la base de datos o el usuario no tiene permisos suficientes')

        vector_info={}
        vector_info['feature_count'] = self.capa.GetFeatureCount()
        extent = self.capa.GetExtent()
        #creamos un ring y lo populamos con las coordenadas del extent
        ring = ogr.Geometry(ogr.wkbLinearRing)
        ring.SetCoordinateDimension(2)
        ring.AddPoint_2D(extent[0],extent[2])
        ring.AddPoint_2D(extent[1], extent[2])
        ring.AddPoint_2D(extent[1], extent[3])
        ring.AddPoint_2D(extent[0], extent[3])
        ring.AddPoint_2D(extent[0],extent[2])
        spatialReference = self.capa.GetSpatialRef()
        if spatialReference is None:
            raise InvalidPostgisLayer('La tabla no tiene referencia espacial')

        spatialReference.AutoIdentifyEPSG()
        auth_code = spatialReference.GetAuthorityCode(None)
        #checamos si ya viene en 4326 y si no, lo ttransformamos
        if auth_code != 4326:
            outSpatialRef = osr.SpatialReference()
            outSpatialRef.ImportFromEPSG(4326)
            coordTrans = osr.CoordinateTransformation(spatialReference, outSpatialRef)
            ring.Transform(coordTrans)

        bbox = [str(extent[1]),str(extent[0]),str(extent[3]),str(extent[2])]
        vector_info['bbox'] = bbox
        #creamos una geometría con el linear ring para poder exportarla como wkt
        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.SetCoordinateDimension(2)
        poly.AddGeometry(ring)
        poly_flat = loads(poly.ExportToWkt())
        vector_info['bbox_wkt'] = poly_flat.wkt
        vector_info['prj_info'] = (auth_code,spatialReference.ExportToWkt())
        lyr_defn = self.capa.GetLayerDefn()
        n_fields = lyr_defn.GetFieldCount()
        geo_type = ogr.GeometryTypeToName(lyr_defn.GetGeomType())
        vector_info['geometry_type'] = geo_type
        vector_info['field_count']=n_fields
        vector_info['att_info']={}
        for iField in range(0,n_fields):
            field_def = lyr_defn.GetFieldDefn(iField)
            f_name = field_def.GetNameRef()
            f_name = f_name.decode('unicode-escape')
            if isinstance(f_name, str):
                log.info('str')
                log.info(f_name)
            elif isinstance(f_name, str):
                log.info('unicode')

            f_type = ogr.GetFieldTypeName(field_def.GetType())
            vector_info['att_info'][f_name]={'tipo':f_type,'descripcion':''}
        if self.type is not None:
            #si estoy leyendo un map index tengo que regresar los nombres de las imágenes que contiene
            vector_info['miembros'] = []
            if lyr_defn.GetFieldIndex('nombre') ==-1:
                vector_info['miembros']= None
            else:
                for feature in self.capa:
                    vector_info['miembros'].append(feature.GetField("nombre"))

        return vector_info


    def getFeatures(self):
        """Regresa una lista con todos los features en una capa"""

        driver = ogr.GetDriverByName('ESRI Shapefile')
        shape = driver.Open(self.shp_path,0)
        if shape is not None:
            self.capa=shape.GetLayer()
        else:
            raise InvalidFormatError('No se pudo leer el archivo')

        features = []
        for feature in self.capa:
            features.append(feature)

        return features
