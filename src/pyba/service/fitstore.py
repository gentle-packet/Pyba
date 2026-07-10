"""On-disk fit library: one JSON file per fit under the user data dir."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .. import paths
from ..fits import Fit, load_fit, save_fit

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.lower()).strip("-")
    return slug or "fit"


@dataclass(frozen=True, slots=True)
class FitInfo:
    slug: str
    name: str
    hero: str
    path: Path


class FitStore:
    def __init__(self, directory: Path | str | None = None) -> None:
        self.directory = Path(directory) if directory else paths.fits_dir()
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, slug: str) -> Path:
        return self.directory / f"{slug}.fit.json"

    def save(self, fit: Fit, slug: str | None = None) -> FitInfo:
        slug = slug or slugify(fit.name or fit.build.hero)
        base, counter = slug, 2
        while self._path(slug).exists() and load_fit(self._path(slug)).name != fit.name:
            slug = f"{base}-{counter}"  # don't clobber a different fit with same slug
            counter += 1
        save_fit(fit, self._path(slug))
        return FitInfo(slug=slug, name=fit.name, hero=fit.build.hero, path=self._path(slug))

    def load(self, slug: str) -> Fit:
        path = self._path(slug)
        if not path.exists():
            raise FileNotFoundError(f"no saved fit {slug!r} in {self.directory}")
        return load_fit(path)

    def delete(self, slug: str) -> None:
        path = self._path(slug)
        if not path.exists():
            raise FileNotFoundError(f"no saved fit {slug!r} in {self.directory}")
        path.unlink()

    def list(self) -> list[FitInfo]:
        infos = []
        for path in sorted(self.directory.glob("*.fit.json")):
            fit = load_fit(path)
            infos.append(
                FitInfo(
                    slug=path.name.removesuffix(".fit.json"),
                    name=fit.name,
                    hero=fit.build.hero,
                    path=path,
                )
            )
        return infos
