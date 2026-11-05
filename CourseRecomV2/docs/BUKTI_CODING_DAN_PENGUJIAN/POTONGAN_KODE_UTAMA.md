# Potongan Kode Utama

Potongan berikut dipilih karena membuktikan titik implementasi utama, bukan sebagai penggantian seluruh source code.

## Double-Submit pada UI

File: `frontend/src/App.jsx`, fungsi `submitStudyPlan`.

```jsx
if (studyPlanSubmissionRef.current) return;
studyPlanSubmissionRef.current = true;
setStudyPlanBusy(true);

const plan = await apiRequest('/mahasiswa/rencana-studi', {
  method: 'POST',
  body: JSON.stringify({ course_codes: draftCourses.map((course) => course.code) }),
});
```

Fungsi menahan submit kedua pada satu instance React dan mengirim kode mata kuliah ke backend.

## Pengajuan KRS dan Validasi Backend

File: `backend/app/api/routes/mahasiswa.py`, fungsi `submit_study_plan`.

```python
if db.query(StudyPlan).filter(
    StudyPlan.student_id == current_user.id,
    StudyPlan.status == 'pending',
).first():
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail='Rencana studi masih menunggu review dosen PA.',
    )

unavailable_codes = sorted(set(payload.course_codes) - set(recommendations_by_code))
if unavailable_codes:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f'Mata kuliah bukan rekomendasi valid untuk semester ini: {", ".join(unavailable_codes)}.',
    )
```

Kode membuktikan bahwa backend memeriksa pending, menghitung rekomendasi valid, lalu menolak kode yang tidak valid.

## Kuota SKS

File yang sama, dalam `submit_study_plan`.

```python
kuota_sks = get_sks_quota(current_user.ipk)
if sum(course['sks'] for course in courses) > kuota_sks:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f'Total SKS melebihi batas maksimum ({kuota_sks} SKS).',
    )
```

## Penyimpanan dan Penanganan IntegrityError

File yang sama.

```python
plan = StudyPlan(
    student_id=current_user.id,
    semester=result['target_semester'],
    courses_json=json.dumps(courses, ensure_ascii=False),
    status='pending',
    advisor_note='',
    created_at=now,
    updated_at=now,
)
db.add(plan)
try:
    db.commit()
except IntegrityError as exc:
    db.rollback()
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail='Rencana studi masih menunggu review dosen PA.',
    ) from exc
```

## Partial Unique Index Database

File: `backend/app/models.py`, model `StudyPlan`.

```python
__table_args__ = (
    Index(
        'uq_study_plans_one_pending_per_student',
        'student_id',
        unique=True,
        sqlite_where=text("status = 'pending'"),
        postgresql_where=text("status = 'pending'"),
    ),
)
```

Index hanya satu pending per mahasiswa tanpa melarang beberapa rencana lama yang tidak pending.

## Review Dosen PA

File: `backend/app/api/routes/dosen.py`, fungsi `review_study_plan`.

```python
if plan.status == 'approved':
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail='KRS yang sudah disetujui tidak dapat diubah.',
    )

plan.status = payload.status
plan.advisor_note = payload.advisor_note
plan.reviewer_id = current_user.id
plan.updated_at = datetime.utcnow()
db.commit()
```

## Bukti Pengujian Database

File: `backend/tests/test_database_config.py`.

Test database menguji bahwa hanya satu rencana pending yang dapat ada untuk satu mahasiswa.
