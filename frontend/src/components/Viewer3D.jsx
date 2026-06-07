import { useEffect, useRef } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { Bounds, Environment, Grid, OrbitControls, useGLTF, Center, GizmoHelper, GizmoViewport } from "@react-three/drei";
import * as THREE from "three";

function Model({ url, wireframe = false, position = [0, 0, 0] }) {
  const gltf = useGLTF(url);
  const scene = gltf.scene.clone();
  
  useEffect(() => {
    scene.traverse((child) => {
      if (child.isMesh) {
        child.material = child.material.clone();
        child.material.wireframe = wireframe;
        child.material.side = THREE.DoubleSide;
        if (!wireframe) {
          child.material.metalness = 0.3;
          child.material.roughness = 0.4;
        }
      }
    });
  }, [scene, wireframe]);
  
  return <primitive object={scene} position={position} />;
}

function CameraReset({ trigger }) {
  const { camera, controls } = useThree();
  
  useEffect(() => {
    if (trigger > 0 && controls) {
      camera.position.set(60, 60, 60);
      camera.lookAt(0, 0, 0);
      controls.target.set(0, 0, 0);
      controls.update();
    }
  }, [trigger, camera, controls]);
  
  return null;
}

function ScreenshotHelper({ onScreenshot }) {
  const { gl, scene, camera } = useThree();
  
  useEffect(() => {
    if (onScreenshot) {
      onScreenshot(() => {
        gl.render(scene, camera);
        return gl.domElement.toDataURL('image/png');
      });
    }
  }, [gl, scene, camera, onScreenshot]);
  
  return null;
}

export default function Viewer3D({ 
  assets, 
  explodeDistance = 0, 
  wireframe = false, 
  showAxis = true, 
  showGrid = true, 
  onScreenshot, 
  resetTrigger = 0,
  apiBase 
}) {
  const canvasRef = useRef();
  const urls = Object.values(assets || {}).map((asset) => `${apiBase}${asset.url}`);

  if (!urls.length) {
    return <div className="viewer-empty">No assembly loaded</div>;
  }

  return (
    <Canvas ref={canvasRef} camera={{ position: [60, 60, 60], fov: 50 }} shadows>
      <color attach="background" args={["#f2f4f7"]} />
      <ambientLight intensity={0.8} />
      <directionalLight position={[50, 80, 50]} intensity={1.5} castShadow />
      <directionalLight position={[-50, -80, -50]} intensity={0.8} />
      <pointLight position={[0, 50, 0]} intensity={0.5} />
      <Center>
        <Bounds fit clip observe margin={2}>
          {urls.map((url, index) => {
            const offset = explodeDistance * (index - urls.length / 2);
            return <Model key={url} url={url} wireframe={wireframe} position={[offset, offset, offset]} />;
          })}
        </Bounds>
      </Center>
      {showGrid && (
        <Grid 
          args={[100, 100]} 
          cellSize={5}
          cellThickness={0.5}
          sectionSize={20}
          sectionThickness={1}
          sectionColor="#9ca3af" 
          cellColor="#d1d5db" 
          fadeDistance={200} 
          fadeStrength={1}
          position={[0, -0.01, 0]}
        />
      )}
      {showAxis && (
        <>
          <axesHelper args={[50]} />
          <GizmoHelper alignment="bottom-right" margin={[80, 80]}>
            <GizmoViewport axisColors={['#ef4444', '#22c55e', '#3b82f6']} labelColor="white" />
          </GizmoHelper>
        </>
      )}
      <OrbitControls makeDefault enableDamping dampingFactor={0.05} minDistance={10} maxDistance={500} />
      <Environment preset="city" />
      <ScreenshotHelper onScreenshot={onScreenshot} />
      <CameraReset trigger={resetTrigger} />
    </Canvas>
  );
}
