from typing import ClassVar, List, Mapping, Sequence, Any, Dict, Optional, Union
from viam.media.video import CameraMimeType
from typing_extensions import Self
from viam.components.camera import Camera
from viam.media.video import RawImage
from viam.proto.service.vision import Classification, Detection
from viam.services.vision import Vision
from viam.module.types import Reconfigurable
from viam.resource.types import Model, ModelFamily
from viam.proto.app.robot import ServiceConfig
from viam.proto.common import PointCloudObject, ResourceName
from viam.resource.base import ResourceBase
from viam.utils import ValueTypes
from viam.logging import getLogger
from .identifier import Identifier
from .utils import decode_image
from PIL import Image

EXTRACTORS = [
  'opencv', 
  'ssd', 
  'dlib', 
  'mtcnn', 
  'retinaface', 
  'mediapipe',
  'yolov8',
  'yunet',
  'fastmtcnn',
]

ENCODERS = [
  "VGG-Face", 
  "Facenet", 
  "Facenet512", 
  "OpenFace", 
  "DeepFace", 
  "DeepID", 
  "ArcFace", 
  "Dlib", 
  "SFace",
]

LOGGER = getLogger(__name__)

class FaceIdentificationModule(Vision, Reconfigurable):
    MODEL: ClassVar[Model] = Model(ModelFamily("viam", "vision"), "deepface-identification")
     
    def __init__(self, name: str):
        super().__init__(name=name)
        
    @classmethod
    def new_service(cls,
                 config: ServiceConfig,
                 dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        service = cls(config.name)
        service.reconfigure(config, dependencies)
        return service
    
     # Validates JSON Configuration
    @classmethod
    def validate_config(cls, config: ServiceConfig) -> Sequence[str]:
        detection_framework = config.attributes.fields["face_extractor_model"].string_value or 'ssd'
        if detection_framework not in EXTRACTORS:
            raise Exception("face_extractor_model must be one of: '" + "', '".join(EXTRACTORS) + "'.")
        model_name = config.attributes.fields["face_embedding_model"].string_value or 'ArcFace'
        if model_name not in ENCODERS:
            raise Exception("face embedding model (encoder) must be one of: '" + "', '".join(ENCODERS) + "'.")
        camera_name = config.attributes.fields["camera_name"].string_value
        if camera_name == "":
            raise Exception(
                "A camera name is required for deepface_identification vision service module.")
        return [camera_name]

    def reconfigure(self,
            config: ServiceConfig,
            dependencies: Mapping[ResourceName, ResourceBase]):
        
        self.camera_name = config.attributes.fields["camera_name"].string_value
        self.camera =  dependencies[Camera.get_resource_name(self.camera_name)]
        def get_attribute_from_config(attribute_name:str,  default, of_type=None):
            if attribute_name not in config.attributes.fields:
                return default

            if default is None:
                if of_type is None:
                    raise Exception("If default value is None, of_type argument can't be empty")
                type_default = of_type
            else:    
                type_default = type(default)

            if type_default == bool:
                return config.attributes.fields[attribute_name].bool_value
            elif type_default == int:
                return int(config.attributes.fields[attribute_name].number_value)
            elif type_default == float:
                return config.attributes.fields[attribute_name].number_value
            elif type_default == str:
                return config.attributes.fields[attribute_name].string_value
            elif type_default == dict:
                return dict(config.attributes.fields[attribute_name].struct_value)
        
        detector_backend = get_attribute_from_config('extractor_model', 'opencv')
        extraction_threshold = get_attribute_from_config('extractor_confidence_threshold', 3)
        grayscale = get_attribute_from_config('grayscale', False)    
        enforce_detection = get_attribute_from_config('enforce_detection', False)
        align = get_attribute_from_config('align', True)
        model_name = get_attribute_from_config('face_embedding_model', 'ArcFace')
        normalization = get_attribute_from_config('normalization', 'base')
        dataset_path = config.attributes.fields['dataset_path'].string_value 
        labels_and_directories = dict(config.attributes.fields['label_and_directories'].struct_value)
        distance_metric_name = get_attribute_from_config('distance_metric', 'cosine')
        identification_threshold = get_attribute_from_config('identification_threshold', None, float)
        sigmoid_steepness = get_attribute_from_config('sigmoid_steepness',10.)
        self.identifier = Identifier(detector_backend=detector_backend, 
                        extraction_threshold=extraction_threshold, 
                        grayscale=grayscale, 
                        enforce_detection = enforce_detection, 
                        align = align,
                        model_name = model_name,
                        normalization= normalization,
                        dataset_path =dataset_path, 
                        labels_directories = labels_and_directories,
                        distance_metric_name = distance_metric_name,
                        identification_threshold=identification_threshold,
                        sigmoid_steepness = sigmoid_steepness)


        self.identifier.compute_known_embeddings()
        LOGGER.info(f" Found {len(self.identifier.known_embeddings)} labelled groups.")
        
    async def get_object_point_clouds(self, camera_name: str, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs) -> List[PointCloudObject]:
        raise NotImplementedError
    
    async def get_detections(self, image: Union[Image.Image, RawImage], *, extra: Mapping[str, Any], timeout: float) -> List[Detection]:
        img = decode_image(image)
        return self.identifier.get_detections(img)
    
    async def get_classifications(self, image: Union[Image.Image, RawImage], count: int, *, extra: Mapping[str, Any]) -> List[Classification]:
        return NotImplementedError
    
    async def get_classifications_from_camera(self) -> List[Classification]:
        return NotImplementedError
    
    async def get_detections_from_camera(self, camera_name: str, *, extra: Mapping[str, Any],  timeout: float) -> List[Detection]:
        im = await self.camera.get_image(mime_type=CameraMimeType.JPEG)
        img = decode_image(im)
        return self.identifier.get_detections(img)
    
    
    async def do_command(self,
                        command: Mapping[str, ValueTypes],
                        *,
                        timeout: Optional[float] = None,
                        **kwargs):
        raise NotImplementedError