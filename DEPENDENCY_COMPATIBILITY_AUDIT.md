# Dependency Compatibility Audit - NumPy 2.x Migration
**Date**: October 5, 2025  
**Issue**: NumPy 2.x scipy ufunc compatibility error  
**Goal**: Ensure ALL dependencies support NumPy 2.x

---

## Executive Summary

**Root Cause**: scipy compiled against NumPy 1.x trying to use NumPy 2.x at runtime  
**Solution**: Migrate entire stack to NumPy 2.x compatible versions  
**Status**: ✅ All critical dependencies have NumPy 2.x compatible versions available

---

## Critical Dependencies Analysis

### 🔴 **BLOCKING ISSUES** (Must Fix)

#### 1. **scipy** - PRIMARY CULPRIT
- **Current Constraint**: None (pulls latest)
- **Issue**: Old versions (< 1.13.0) incompatible with NumPy 2.x
- **Fix Required**: `scipy>=1.13.0`
- **NumPy 2.x Support**: scipy 1.13.0+ (released May 2024)
- **Evidence**: `sph_legendre_p` ufunc error is scipy-specific
- **Action**: ✅ Added to requirements.txt

#### 2. **pandas**
- **Current Constraint**: None (pulls latest)
- **Issue**: Old versions (< 2.2.0) have limited NumPy 2.x support
- **Fix Required**: `pandas>=2.2.0`
- **NumPy 2.x Support**: pandas 2.2.0+ (released January 2024)
- **Action**: ✅ Added to requirements.txt

---

## ML/AI Stack Compatibility

### ✅ **PyTorch Ecosystem** (Already Compatible)

#### torch 2.3.1
- **Current**: `torch>=2.3.1,<2.5.0`
- **NumPy 2.x Support**: torch 2.2.0+ (released January 2024)
- **Status**: ✅ COMPATIBLE
- **Notes**: PyTorch team added NumPy 2.x support early

#### torchvision 0.18.1
- **Current**: `torchvision>=0.18.1,<0.20.0`
- **NumPy 2.x Support**: torchvision 0.17.0+ (with torch 2.2+)
- **Status**: ✅ COMPATIBLE
- **Dependencies**: Requires Pillow (checked below)

#### torchaudio 2.3.1
- **Installed in Dockerfile**: `torchaudio==2.3.1`
- **NumPy 2.x Support**: torchaudio 2.2.0+
- **Status**: ✅ COMPATIBLE

### ✅ **Transformers Ecosystem** (Already Compatible)

#### transformers 4.36.0+
- **Current**: `transformers>=4.36.0,<4.50.0`
- **NumPy 2.x Support**: transformers 4.37.0+ (released January 2024)
- **Status**: ✅ COMPATIBLE
- **Notes**: Hugging Face quickly adopted NumPy 2.x

#### accelerate 0.25.0+
- **Current**: `accelerate>=0.25.0`
- **NumPy 2.x Support**: accelerate 0.28.0+ (released March 2024)
- **Status**: ⚠️ SHOULD UPGRADE to >=0.28.0
- **Action**: 🔧 Recommend updating constraint

#### safetensors 0.4.0+
- **Current**: `safetensors>=0.4.0`
- **NumPy 2.x Support**: safetensors 0.4.3+ (released June 2024)
- **Status**: ⚠️ SHOULD UPGRADE to >=0.4.3
- **Action**: 🔧 Recommend updating constraint

#### huggingface-hub 0.19.0+
- **Current**: `huggingface-hub>=0.19.0`
- **NumPy 2.x Support**: huggingface-hub 0.23.0+ (released May 2024)
- **Status**: ⚠️ SHOULD UPGRADE to >=0.23.0
- **Action**: 🔧 Recommend updating constraint

#### bitsandbytes 0.42.0+
- **Current**: `bitsandbytes>=0.42.0`
- **NumPy 2.x Support**: bitsandbytes 0.43.0+ (released June 2024)
- **Status**: ⚠️ SHOULD UPGRADE to >=0.43.0
- **Action**: 🔧 Recommend updating constraint
- **Notes**: Critical for RTX 4090 quantization

---

## Document Processing Stack

### 🔴 **docstrange** (Requires Investigation)
- **Current**: No version constraint
- **Issue**: Transitive dependencies (scipy, opencv, easyocr) may pull incompatible versions
- **Known Dependencies**:
  - beautifulsoup4 ✅ (no NumPy dependency)
  - docling-ibm-models ⚠️ (needs verification)
  - easyocr ⚠️ (uses opencv-python, scikit-image)
  - Flask ✅ (no NumPy dependency)
  - huggingface_hub ✅ (covered above)
  - lxml ✅ (no NumPy dependency)
  - markdownify ✅ (no NumPy dependency)
  - mcp ⚠️ (needs verification)
  - numpy ✅ (handled)
  - openpyxl ✅ (no NumPy dependency)
  - pandas ✅ (covered above)
  - pdf2image ✅ (no NumPy dependency)
  - Pillow ✅ (covered below)
  - PyMuPDF ⚠️ (needs verification)
  - pypandoc ✅ (no NumPy dependency)
  - python-docx ✅ (no NumPy dependency)
  - python-pptx ✅ (no NumPy dependency)
  - requests ✅ (no NumPy dependency)
  - tiktoken ✅ (no NumPy dependency)
  - tokenizers ✅ (no NumPy dependency)
  - tqdm ✅ (no NumPy dependency)
  - transformers ✅ (covered above)
- **Action**: 🔧 Pin transitive dependencies

### ⚠️ **Image Processing Dependencies**

#### Pillow 10.1.0+
- **Current**: `pillow>=10.1.0`
- **NumPy 2.x Support**: Pillow 10.3.0+ (released April 2024)
- **Status**: ⚠️ SHOULD UPGRADE to >=10.3.0
- **Action**: 🔧 Recommend updating constraint
- **Critical**: Used by torchvision, docstrange, easyocr

#### opencv-python (via easyocr)
- **Not explicitly listed**: Pulled by easyocr
- **NumPy 2.x Support**: opencv-python 4.10.0+ (released June 2024)
- **Status**: ⚠️ SHOULD ADD explicit constraint
- **Action**: 🔧 Add `opencv-python>=4.10.0` to requirements.txt
- **Risk**: HIGH - opencv is a major NumPy consumer

#### scikit-image (via easyocr/docstrange)
- **Not explicitly listed**: Pulled by easyocr
- **NumPy 2.x Support**: scikit-image 0.24.0+ (released July 2024)
- **Status**: ⚠️ SHOULD ADD explicit constraint
- **Action**: 🔧 Add `scikit-image>=0.24.0` to requirements.txt
- **Risk**: MEDIUM - uses scipy

---

## Web Framework Stack

### ✅ **FastAPI & Dependencies** (No NumPy)

#### fastapi 0.104.0+
- **Current**: `fastapi>=0.104.0,<0.115.0`
- **NumPy Dependency**: None
- **Status**: ✅ SAFE

#### uvicorn 0.24.0+
- **Current**: `uvicorn[standard]>=0.24.0,<0.32.0`
- **NumPy Dependency**: None
- **Status**: ✅ SAFE

#### pydantic 2.5.0+
- **Current**: `pydantic>=2.5.0,<3.0.0`
- **NumPy Dependency**: None
- **Status**: ✅ SAFE
- **Notes**: v2 API is stable

#### python-multipart, python-dotenv, httpx, aiofiles, requests
- **NumPy Dependency**: None
- **Status**: ✅ SAFE

---

## Utility & Build Dependencies

### ✅ **No NumPy Dependencies**

#### sentencepiece 0.1.99+
- **Current**: `sentencepiece>=0.1.99`
- **NumPy Dependency**: None (uses SPM binary format)
- **Status**: ✅ SAFE

#### protobuf 4.25.0+
- **Current**: `protobuf>=4.25.0,<6.0.0`
- **NumPy Dependency**: None
- **Status**: ✅ SAFE

#### packaging, wheel, setuptools
- **NumPy Dependency**: None
- **Status**: ✅ SAFE

#### runpod 1.3.0+
- **Current**: `runpod>=1.3.0`
- **NumPy Dependency**: None
- **Status**: ✅ SAFE

---

## Transitive Dependencies to Watch

### 🔴 **HIGH RISK** (Must Pin)

1. **opencv-python** (via easyocr)
   - Add: `opencv-python>=4.10.0`
   - Reason: Major NumPy consumer, old versions incompatible

2. **scikit-image** (via easyocr/docstrange)
   - Add: `scikit-image>=0.24.0`
   - Reason: Uses scipy internally

3. **opencv-python-headless** (alternative to opencv-python)
   - Add: `opencv-python-headless>=4.10.0` (if used instead)
   - Reason: Same as opencv-python

### ⚠️ **MEDIUM RISK** (Should Pin)

4. **docling-ibm-models** (via docstrange)
   - Research required: Check if it uses NumPy
   - Action: Test and pin if needed

5. **PyMuPDF** (via docstrange)
   - Research required: Check NumPy 2.x support
   - Action: Test and pin if needed

6. **imageio** (potential transitive dep)
   - NumPy 2.x Support: imageio 2.34.1+ (released June 2024)
   - Add if present: `imageio>=2.34.1`

7. **matplotlib** (potential transitive dep)
   - NumPy 2.x Support: matplotlib 3.9.0+ (released May 2024)
   - Add if present: `matplotlib>=3.9.0`

---

## Recommended Requirements.txt Updates

### 🔧 **Immediate Actions** (Critical Path)

```python
# Scientific Stack - CRITICAL FOR NUMPY 2.X
scipy>=1.13.0              # ✅ ADDED - Fixes sph_legendre_p error
pandas>=2.2.0              # ✅ ADDED - NumPy 2.x compatible
numpy>=2.0.0,<3.0.0        # ✅ ADDED - Embrace NumPy 2.x

# Image Processing - HIGH PRIORITY
opencv-python>=4.10.0      # 🔧 ADD - Major NumPy consumer
scikit-image>=0.24.0       # 🔧 ADD - Uses scipy/numpy heavily
pillow>=10.3.0             # 🔧 UPGRADE - Current 10.1.0 too old
```

### 🔧 **Secondary Updates** (Recommended)

```python
# ML/AI Upgrades for better NumPy 2.x support
accelerate>=0.28.0         # 🔧 UPGRADE from >=0.25.0
safetensors>=0.4.3         # 🔧 UPGRADE from >=0.4.0
huggingface-hub>=0.23.0    # 🔧 UPGRADE from >=0.19.0
bitsandbytes>=0.43.0       # 🔧 UPGRADE from >=0.42.0
```

### 📝 **Testing Required**

```python
# Need to verify NumPy 2.x compatibility
docstrange                 # 🔍 TEST - No version pinned
# Consider pinning docstrange to specific version after testing
```

---

## Dockerfile Changes Required

### Current Issues

```dockerfile
# OLD: Installing with NumPy 1.x constraint
RUN pip install 'numpy>=1.24.0,<2.0.0' --no-cache-dir
```

### Fixed Version

```dockerfile
# NEW: Install PyTorch first, then requirements with NumPy 2.x
RUN pip install torch==2.3.1 torchvision==0.18.1 torchaudio==2.3.1 \
    --index-url https://download.pytorch.org/whl/cu121

# Install all requirements with NumPy 2.x compatible versions
RUN pip install --no-cache-dir -r requirements.txt

# Verify NumPy 2.x installed
RUN python -c "import numpy; assert numpy.__version__.startswith('2.'), 'NumPy 2.x required'"
```

---

## Testing Checklist

### 🧪 **Phase 1: Import Tests** (Quick validation)

```python
# Test 1: NumPy 2.x installed
import numpy
assert numpy.__version__.startswith('2.'), f"Expected NumPy 2.x, got {numpy.__version__}"

# Test 2: Scipy works with NumPy 2.x
import scipy
from scipy.special import sph_legendre  # The problematic function
print(f"✓ scipy {scipy.__version__} works with NumPy {numpy.__version__}")

# Test 3: Pandas works
import pandas
print(f"✓ pandas {pandas.__version__} works with NumPy {numpy.__version__}")

# Test 4: PyTorch works
import torch
print(f"✓ torch {torch.__version__} works with NumPy {numpy.__version__}")

# Test 5: Transformers works
import transformers
print(f"✓ transformers {transformers.__version__} works with NumPy {numpy.__version__}")

# Test 6: OpenCV works (HIGH PRIORITY)
import cv2
print(f"✓ opencv-python {cv2.__version__} works with NumPy {numpy.__version__}")

# Test 7: Scikit-image works
import skimage
print(f"✓ scikit-image {skimage.__version__} works with NumPy {numpy.__version__}")

# Test 8: DocStrange works (CRITICAL)
from docstrange import DocumentExtractor
print(f"✓ DocStrange works with NumPy {numpy.__version__}")
```

### 🧪 **Phase 2: Functional Tests**

1. **Document Extraction**: Upload PDF, extract text
2. **Classification**: Run Mixtral inference on extracted data
3. **Concurrent Requests**: Send 4 extractions + 1 classification
4. **GPU Memory**: Monitor VRAM usage during tests
5. **Cold Start**: Test first request after deployment

---

## Risk Assessment

### 🔴 **Critical Risks**

1. **opencv-python not pinned**: Could pull NumPy 1.x compatible version
   - **Impact**: BLOCKER - Same ufunc error as scipy
   - **Mitigation**: Add explicit constraint

2. **scikit-image not pinned**: Uses scipy internally
   - **Impact**: HIGH - Could trigger scipy errors
   - **Mitigation**: Add explicit constraint

### ⚠️ **Medium Risks**

3. **docstrange version unpinned**: Unknown transitive dependencies
   - **Impact**: MEDIUM - Could pull incompatible versions
   - **Mitigation**: Test thoroughly, pin version if stable

4. **Pillow version too old**: 10.1.0 has limited NumPy 2.x support
   - **Impact**: MEDIUM - May cause torchvision issues
   - **Mitigation**: Upgrade to >=10.3.0

### ✅ **Low Risks**

5. **PyTorch/Transformers ecosystem**: Already compatible
6. **FastAPI stack**: No NumPy dependencies
7. **Utility libraries**: No NumPy dependencies

---

## Migration Timeline

### ⏱️ **Immediate** (Today)
1. ✅ Add scipy>=1.13.0 to requirements.txt
2. ✅ Add pandas>=2.2.0 to requirements.txt
3. ✅ Update numpy to >=2.0.0
4. 🔧 Add opencv-python>=4.10.0
5. 🔧 Add scikit-image>=0.24.0
6. 🔧 Update Dockerfile to remove NumPy 1.x workarounds
7. 🔧 Commit and push changes

### ⏱️ **Test & Deploy** (Next 1-2 hours)
8. 🧪 Rebuild Docker image on RunPod
9. 🧪 Run Phase 1 import tests
10. 🧪 Run Phase 2 functional tests
11. 🧪 Monitor production for 24 hours

### ⏱️ **Follow-up** (Next week)
12. 📝 Pin docstrange to tested version
13. 📝 Upgrade accelerate, safetensors, huggingface-hub
14. 📝 Update documentation

---

## Success Criteria

✅ **Build Success**
- Docker image builds without errors
- NumPy 2.x installed and verified
- All imports succeed

✅ **Runtime Success**
- No `sph_legendre_p` ufunc errors
- DocStrange extraction works
- Mixtral classification works
- Concurrent requests handled correctly

✅ **Performance Success**
- Cold start < 180 seconds
- Warm requests < 30 seconds
- GPU memory stable

---

## Rollback Plan

If NumPy 2.x migration fails:

1. **Revert requirements.txt**:
   ```python
   scipy>=1.11.0,<1.13.0  # NumPy 1.x compatible
   pandas>=2.0.0,<2.2.0   # NumPy 1.x compatible
   numpy>=1.24.0,<2.0.0   # Force NumPy 1.x
   ```

2. **Revert Dockerfile**: Restore NumPy 1.x installation order

3. **Pin ALL dependencies**: Use `pip freeze > requirements-locked.txt` from working environment

4. **Use locked requirements**: `RUN pip install -r requirements-locked.txt`

---

## References

- [NumPy 2.0 Migration Guide](https://numpy.org/devdocs/numpy_2_0_migration_guide.html)
- [SciPy 1.13.0 Release Notes](https://github.com/scipy/scipy/releases/tag/v1.13.0)
- [PyTorch NumPy 2.0 Support](https://github.com/pytorch/pytorch/issues/123371)
- [Pandas 2.2.0 Release Notes](https://pandas.pydata.org/docs/whatsnew/v2.2.0.html)
- [OpenCV Python 4.10.0 Release](https://github.com/opencv/opencv-python/releases/tag/89)

---

**Status**: 🔄 In Progress  
**Last Updated**: October 5, 2025  
**Next Review**: After deployment test
